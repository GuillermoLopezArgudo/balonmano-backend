from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/partidos", tags=["partidos"])


def _club_nombre(equipo: models.Equipo | None) -> str | None:
    if not equipo:
        return None
    return equipo.datos.nombre if equipo.datos else None


def _partido_out(partido: models.Partido) -> schemas.PartidoOut:
    rival_nombre = partido.rival.nombre if partido.rival else None
    owner = partido.equipo_owner
    owner_nombre = _club_nombre(owner)

    if partido.id_rival and partido.id_equipo:
        es_local = bool(partido.es_local) if partido.es_local is not None else True
        local_nombre = owner_nombre if es_local else rival_nombre
        visit_nombre = rival_nombre if es_local else owner_nombre
        # IDs sintetizados para que el FE compare con equipo.id_equipo
        id_local = partido.id_equipo if es_local else partido.id_rival
        id_visit = partido.id_rival if es_local else partido.id_equipo
    else:
        local_nombre = _club_nombre(partido.equipo_local)
        visit_nombre = _club_nombre(partido.equipo_visitante)
        id_local = partido.id_equipo_local
        id_visit = partido.id_equipo_visitante
        es_local = None

    return schemas.PartidoOut(
        id_partido=partido.id_partido,
        id_equipo_local=id_local,
        id_equipo_visitante=id_visit,
        id_equipo=partido.id_equipo,
        id_rival=partido.id_rival,
        es_local=es_local if es_local is not None else (
            bool(partido.es_local) if partido.es_local is not None else None
        ),
        id_temporada=partido.id_temporada,
        fecha=partido.fecha,
        jornada=partido.jornada,
        pabellon=partido.pabellon,
        competicion=partido.competicion,
        img_portada=getattr(partido, "img_portada", None),
        goles_local=partido.goles_local,
        goles_visitante=partido.goles_visitante,
        estado=getattr(partido, "estado", None) or "programado",
        equipo_local_nombre=local_nombre,
        equipo_visitante_nombre=visit_nombre,
        temporada_nombre=partido.temporada.nombre if partido.temporada else None,
        temporada_estado=partido.temporada.estado if partido.temporada else None,
    )


def _load(db: Session, id_partido: str) -> models.Partido | None:
    return (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.equipo_local).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_visitante).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_owner).joinedload(models.Equipo.datos),
            joinedload(models.Partido.rival),
            joinedload(models.Partido.temporada),
        )
        .filter(models.Partido.id_partido == id_partido)
        .first()
    )


def _assert_editable(partido: models.Partido) -> None:
    temp = partido.temporada
    if not temp:
        return
    if temp.estado == "archivada":
        raise HTTPException(status_code=400, detail="Temporada archivada: no se puede editar")
    if temp.estado == "cerrada" and partido.estado not in ("programado", "aplazado"):
        raise HTTPException(
            status_code=400,
            detail="En temporada cerrada solo se pueden completar partidos aplazados/programados",
        )


def _scope_filter(id_equipo):
    return or_(
        models.Partido.id_equipo == id_equipo,
        models.Partido.id_equipo_local == id_equipo,
        models.Partido.id_equipo_visitante == id_equipo,
    )


@router.get("/", response_model=list[schemas.PartidoOut])
def listar(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    partidos = (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.equipo_local).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_visitante).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_owner).joinedload(models.Equipo.datos),
            joinedload(models.Partido.rival),
            joinedload(models.Partido.temporada),
        )
        .filter(_scope_filter(equipo.id_equipo))
        .order_by(models.Partido.fecha.desc())
        .all()
    )
    return [_partido_out(p) for p in partidos]


@router.post("/", response_model=schemas.PartidoOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: schemas.PartidoCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    rival = (
        db.query(models.Rival)
        .filter(
            models.Rival.id_rival == payload.id_rival,
            models.Rival.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not rival:
        raise HTTPException(status_code=404, detail="Rival no encontrado")

    temporada = db.get(models.Temporada, payload.id_temporada)
    if not temporada:
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    if temporada.id_equipo and temporada.id_equipo != equipo.id_equipo:
        raise HTTPException(status_code=403, detail="Temporada de otro club")
    # Legacy seasons without owner: must be linked via EquipoTemporada
    if not temporada.id_equipo:
        link = db.get(
            models.EquipoTemporada,
            {"id_equipo": equipo.id_equipo, "id_temporada": temporada.id_temporada},
        )
        if not link:
            raise HTTPException(status_code=403, detail="Temporada de otro club")
    if temporada.estado != "activa":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden crear partidos en la temporada activa",
        )

    es_local = payload.es_local
    partido = models.Partido(
        id_equipo=equipo.id_equipo,
        id_rival=rival.id_rival,
        es_local=es_local,
        id_equipo_local=equipo.id_equipo if es_local else None,
        id_equipo_visitante=equipo.id_equipo if not es_local else None,
        id_temporada=payload.id_temporada,
        fecha=payload.fecha,
        jornada=payload.jornada,
        pabellon=payload.pabellon,
        competicion=payload.competicion,
        img_portada=payload.img_portada,
        goles_local=payload.goles_local,
        goles_visitante=payload.goles_visitante,
        estado=payload.estado or "programado",
    )
    db.add(partido)
    db.commit()
    return _partido_out(_load(db, str(partido.id_partido)))


@router.patch("/{id_partido}", response_model=schemas.PartidoOut)
def actualizar(
    id_partido: str,
    payload: schemas.PartidoUpdate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    if not partido_del_equipo(db, id_partido, equipo.id_equipo):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    partido = _load(db, id_partido)
    _assert_editable(partido)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(partido, key, value)
    db.commit()
    return _partido_out(_load(db, id_partido))


@router.delete("/{id_partido}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    id_partido: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    partido = partido_del_equipo(db, id_partido, equipo.id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    partido = _load(db, id_partido)
    if partido.temporada and partido.temporada.estado == "archivada":
        raise HTTPException(
            status_code=400, detail="No se puede borrar un partido de temporada archivada"
        )
    db.delete(partido)
    db.commit()
