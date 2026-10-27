from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo, get_equipo_area
from app.database import get_db
from app.services.partidos_service import (
    assert_editable,
    load_partido,
    partido_out,
    scope_filter,
)

router = APIRouter(prefix="/partidos", tags=["partidos"])


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
        .filter(scope_filter(equipo.id_equipo))
        .order_by(models.Partido.fecha.desc())
        .all()
    )
    return [partido_out(p) for p in partidos]


@router.get("/{id_partido}", response_model=schemas.PartidoOut)
def obtener(
    id_partido: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    if not partido_del_equipo(db, id_partido, equipo.id_equipo):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    partido = load_partido(db, id_partido)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido_out(partido)


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
        goles_local=payload.goles_local,
        goles_visitante=payload.goles_visitante,
        estado=payload.estado or "programado",
    )
    db.add(partido)
    db.commit()
    return partido_out(load_partido(db, str(partido.id_partido)))


@router.patch("/{id_partido}", response_model=schemas.PartidoOut)
def actualizar(
    id_partido: str,
    payload: schemas.PartidoUpdate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    if not partido_del_equipo(db, id_partido, equipo.id_equipo):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    partido = load_partido(db, id_partido)
    assert_editable(partido)

    data = payload.model_dump(exclude_unset=True)

    if "id_rival" in data and data["id_rival"] is not None:
        rival = (
            db.query(models.Rival)
            .filter(
                models.Rival.id_rival == data["id_rival"],
                models.Rival.id_equipo == equipo.id_equipo,
            )
            .first()
        )
        if not rival:
            raise HTTPException(status_code=404, detail="Rival no encontrado")
        partido.id_rival = rival.id_rival

    if "es_local" in data and data["es_local"] is not None:
        es_local = bool(data["es_local"])
        partido.es_local = es_local
        partido.id_equipo_local = equipo.id_equipo if es_local else None
        partido.id_equipo_visitante = equipo.id_equipo if not es_local else None

    for key, value in data.items():
        if key in ("id_rival", "es_local"):
            continue
        setattr(partido, key, value)
    db.commit()
    return partido_out(load_partido(db, id_partido))


@router.delete("/{id_partido}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    id_partido: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    partido = partido_del_equipo(db, id_partido, equipo.id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    partido = load_partido(db, id_partido)
    if partido.temporada and partido.temporada.estado == "archivada":
        raise HTTPException(
            status_code=400, detail="No se puede borrar un partido de temporada archivada"
        )
    db.delete(partido)
    db.commit()
