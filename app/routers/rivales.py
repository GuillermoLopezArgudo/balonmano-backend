from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/rivales", tags=["rivales"])

ZONA_LABELS = {
    "ext_izq": "Ext. izq.",
    "ext_der": "Ext. der.",
    "6m_izq": "6 m izq.",
    "6m_cen": "6 m / pivote",
    "6m_der": "6 m der.",
    "9m_izq": "9 m izq.",
    "9m_cen": "9 m centro",
    "9m_der": "9 m der.",
    "7m": "7 m",
}


def _assert_rival(db: Session, id_rival, id_equipo) -> models.Rival:
    rival = (
        db.query(models.Rival)
        .filter(models.Rival.id_rival == id_rival, models.Rival.id_equipo == id_equipo)
        .first()
    )
    if not rival:
        raise HTTPException(status_code=404, detail="Rival no encontrado")
    return rival


@router.get("/", response_model=list[schemas.RivalOut])
def listar(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    return (
        db.query(models.Rival)
        .filter(models.Rival.id_equipo == equipo.id_equipo)
        .order_by(models.Rival.nombre)
        .all()
    )


@router.post("/", response_model=schemas.RivalOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: schemas.RivalCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre obligatorio")
    existente = (
        db.query(models.Rival)
        .filter(
            models.Rival.id_equipo == equipo.id_equipo,
            models.Rival.nombre.ilike(nombre),
        )
        .first()
    )
    if existente:
        return existente
    rival = models.Rival(id_equipo=equipo.id_equipo, nombre=nombre)
    db.add(rival)
    db.commit()
    db.refresh(rival)
    return rival


@router.delete("/{id_rival}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    id_rival: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    rival = _assert_rival(db, id_rival, equipo.id_equipo)
    usados = db.query(models.Partido).filter(models.Partido.id_rival == id_rival).count()
    if usados:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar: el rival tiene partidos asociados",
        )
    db.delete(rival)
    db.commit()


@router.get("/partido/{id_partido}/goleadoras", response_model=list[schemas.RivalGoleadoraOut])
def goleadoras_partido(
    id_partido: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    """Ranking de dorsales rivales con más goles en este partido + zona top."""
    partido = (
        db.query(models.Partido)
        .filter(models.Partido.id_partido == id_partido)
        .first()
    )
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    from app.auth import partido_del_equipo

    if not partido_del_equipo(db, id_partido, equipo.id_equipo):
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    tipo = db.query(models.TipoAccion).filter(models.TipoAccion.nombre == "Gol recibido").first()
    if not tipo:
        return []

    acciones = (
        db.query(models.Accion)
        .options(joinedload(models.Accion.rival_jugador))
        .filter(
            models.Accion.id_partido == id_partido,
            models.Accion.id_tipo_accion == tipo.id_tipo_accion,
        )
        .all()
    )

    buckets: dict[str, dict] = {}
    for a in acciones:
        key = str(a.id_rival_jugador) if a.id_rival_jugador else "_sin"
        if key not in buckets:
            rj = a.rival_jugador
            buckets[key] = {
                "id_rival_jugador": a.id_rival_jugador,
                "dorsal": rj.dorsal if rj else None,
                "nombre": rj.nombre if rj else None,
                "goles": 0,
                "zonas": Counter(),
            }
        buckets[key]["goles"] += 1
        if a.zona:
            buckets[key]["zonas"][a.zona] += 1

    out: list[schemas.RivalGoleadoraOut] = []
    for row in buckets.values():
        zonas = dict(row["zonas"])
        zona_top = None
        if zonas:
            zona_top = max(zonas.items(), key=lambda x: x[1])[0]
        out.append(
            schemas.RivalGoleadoraOut(
                id_rival_jugador=row["id_rival_jugador"],
                dorsal=row["dorsal"],
                nombre=row["nombre"],
                goles=row["goles"],
                zona_top=zona_top,
                zona_top_label=ZONA_LABELS.get(zona_top or "", zona_top),
                zonas=zonas,
            )
        )
    out.sort(key=lambda x: (-x.goles, x.dorsal if x.dorsal is not None else 999))
    return out


@router.get("/{id_rival}/jugadoras", response_model=list[schemas.RivalJugadorOut])
def listar_jugadoras(
    id_rival: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _assert_rival(db, id_rival, equipo.id_equipo)
    return (
        db.query(models.RivalJugador)
        .filter(
            models.RivalJugador.id_rival == id_rival,
            models.RivalJugador.activo.is_(True),
        )
        .order_by(models.RivalJugador.dorsal)
        .all()
    )


@router.post(
    "/{id_rival}/jugadoras",
    response_model=schemas.RivalJugadorOut,
    status_code=status.HTTP_201_CREATED,
)
def upsert_jugadora(
    id_rival: str,
    payload: schemas.RivalJugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("partidos")),
):
    _assert_rival(db, id_rival, equipo.id_equipo)
    existente = (
        db.query(models.RivalJugador)
        .filter(
            models.RivalJugador.id_rival == id_rival,
            models.RivalJugador.dorsal == payload.dorsal,
        )
        .first()
    )
    if existente:
        if payload.nombre is not None:
            existente.nombre = payload.nombre.strip() or None
        existente.activo = True
        db.commit()
        db.refresh(existente)
        return existente

    fila = models.RivalJugador(
        id_rival=id_rival,
        dorsal=payload.dorsal,
        nombre=(payload.nombre or "").strip() or None,
        activo=True,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila
