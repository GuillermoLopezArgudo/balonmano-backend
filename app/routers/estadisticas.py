from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo
from app.database import get_db

router = APIRouter(prefix="/estadisticas", tags=["estadisticas"])


def _assert_partido(db: Session, id_partido, id_equipo) -> models.Partido:
    partido = partido_del_equipo(db, id_partido, id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


def _assert_jugador_club(db: Session, id_jugador, id_equipo) -> None:
    vinculo = (
        db.query(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_jugador == id_jugador,
            models.JugadorEquipo.id_equipo == id_equipo,
        )
        .first()
    )
    if not vinculo:
        raise HTTPException(status_code=403, detail="Jugador no pertenece a tu equipo")


def _partidos_ids(db: Session, id_equipo):
    rows = (
        db.query(models.Partido.id_partido)
        .filter(
            or_(
                models.Partido.id_equipo == id_equipo,
                models.Partido.id_equipo_local == id_equipo,
                models.Partido.id_equipo_visitante == id_equipo,
            )
        )
        .all()
    )
    return [r[0] for r in rows]


@router.get("/jugadores/", response_model=list[schemas.EstadisticaJugadorOut])
def listar_jugador(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaJugador)
        .filter(models.EstadisticaJugador.id_partido.in_(ids))
        .order_by(models.EstadisticaJugador.id_estadistica.desc())
        .all()
    )


@router.post(
    "/jugadores/",
    response_model=schemas.EstadisticaJugadorOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_jugador(
    payload: schemas.EstadisticaJugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    existe = (
        db.query(models.EstadisticaJugador)
        .filter(
            models.EstadisticaJugador.id_partido == payload.id_partido,
            models.EstadisticaJugador.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if existe:
        for key, value in payload.model_dump().items():
            if key in ("id_partido", "id_jugador"):
                continue
            setattr(existe, key, value)
        db.commit()
        db.refresh(existe)
        return existe
    fila = models.EstadisticaJugador(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/jugadores/", response_model=schemas.EstadisticaJugadorOut)
def upsert_jugador(
    payload: schemas.EstadisticaJugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    return crear_jugador(payload, db, equipo)


@router.get("/lanzamientos/", response_model=list[schemas.EstadisticaLanzamientoOut])
def listar_lanzamiento(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaLanzamiento)
        .filter(models.EstadisticaLanzamiento.id_partido.in_(ids))
        .order_by(models.EstadisticaLanzamiento.id_estadistica.desc())
        .all()
    )


@router.post(
    "/lanzamientos/",
    response_model=schemas.EstadisticaLanzamientoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_lanzamiento(
    payload: schemas.EstadisticaLanzamientoCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    fila = models.EstadisticaLanzamiento(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.get("/porteros/", response_model=list[schemas.EstadisticaPorteroOut])
def listar_portero(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaPortero)
        .filter(models.EstadisticaPortero.id_partido.in_(ids))
        .order_by(models.EstadisticaPortero.id_estadistica.desc())
        .all()
    )


@router.post(
    "/porteros/",
    response_model=schemas.EstadisticaPorteroOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_portero(
    payload: schemas.EstadisticaPorteroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    existe = (
        db.query(models.EstadisticaPortero)
        .filter(
            models.EstadisticaPortero.id_partido == payload.id_partido,
            models.EstadisticaPortero.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if existe:
        for key, value in payload.model_dump().items():
            if key in ("id_partido", "id_jugador"):
                continue
            setattr(existe, key, value)
        db.commit()
        db.refresh(existe)
        return existe
    fila = models.EstadisticaPortero(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/porteros/", response_model=schemas.EstadisticaPorteroOut)
def upsert_portero(
    payload: schemas.EstadisticaPorteroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    return crear_portero(payload, db, equipo)


@router.get("/acciones/", response_model=list[schemas.AccionOut])
def listar_acciones(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.Accion)
        .filter(models.Accion.id_partido.in_(ids))
        .order_by(models.Accion.minuto, models.Accion.segundo)
        .all()
    )


@router.post("/acciones/", response_model=schemas.AccionOut, status_code=status.HTTP_201_CREATED)
def crear_accion(
    payload: schemas.AccionCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    tipo = db.get(models.TipoAccion, payload.id_tipo_accion)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de acción no encontrado")
    fila = models.Accion(**payload.model_dump())
    db.add(fila)

    stats = (
        db.query(models.EstadisticaJugador)
        .filter(
            models.EstadisticaJugador.id_partido == payload.id_partido,
            models.EstadisticaJugador.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if not stats:
        stats = models.EstadisticaJugador(
            id_partido=payload.id_partido,
            id_jugador=payload.id_jugador,
        )
        db.add(stats)
        db.flush()

    nombre = tipo.nombre.lower()
    if "gol" in nombre and "recibid" not in nombre:
        stats.goles += 1
        stats.lanzamientos += 1
    elif "lanzamiento" in nombre or "fallado" in nombre or "fuera" in nombre or "poste" in nombre:
        stats.lanzamientos += 1
        stats.lanzamientos_fallados += 1
    elif "asistencia" in nombre:
        stats.asistencias += 1
    elif "pérdida" in nombre or "perdida" in nombre:
        stats.perdidas += 1
    elif "recuperación" in nombre or "recuperacion" in nombre:
        stats.recuperaciones += 1
    elif "exclusión" in nombre or "exclusion" in nombre:
        stats.exclusiones_2min += 1
    elif "amarilla" in nombre:
        stats.amarillas += 1
    elif "roja" in nombre:
        stats.rojas += 1

    db.commit()
    db.refresh(fila)
    return fila


@router.get("/resumen/jugadores", response_model=list[schemas.ResumenJugador])
def resumen_jugadores(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    jugador_ids = [
        r[0]
        for r in db.query(models.JugadorEquipo.id_jugador)
        .filter(models.JugadorEquipo.id_equipo == equipo.id_equipo)
        .all()
    ]
    if not jugador_ids:
        return []
    filas = (
        db.query(
            models.Jugador.id_jugador,
            models.Jugador.nombre,
            models.Jugador.apellido,
            func.count(models.EstadisticaJugador.id_estadistica).label("partidos"),
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0).label("goles"),
            func.coalesce(func.sum(models.EstadisticaJugador.asistencias), 0).label("asistencias"),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0).label("lanzamientos"),
            func.coalesce(func.sum(models.EstadisticaJugador.exclusiones_2min), 0).label(
                "exclusiones_2min"
            ),
            func.coalesce(func.sum(models.EstadisticaJugador.minutos_jugados), 0).label(
                "minutos_jugados"
            ),
        )
        .outerjoin(
            models.EstadisticaJugador,
            models.EstadisticaJugador.id_jugador == models.Jugador.id_jugador,
        )
        .filter(models.Jugador.id_jugador.in_(jugador_ids))
        .group_by(models.Jugador.id_jugador, models.Jugador.nombre, models.Jugador.apellido)
        .order_by(func.coalesce(func.sum(models.EstadisticaJugador.goles), 0).desc())
        .all()
    )
    return [schemas.ResumenJugador.model_validate(fila._mapping) for fila in filas]


@router.delete("/jugadores/{id_estadistica}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_jugador(
    id_estadistica: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    fila = db.get(models.EstadisticaJugador, id_estadistica)
    if not fila:
        raise HTTPException(status_code=404, detail="Estadística no encontrada")
    _assert_partido(db, fila.id_partido, equipo.id_equipo)
    db.delete(fila)
    db.commit()
