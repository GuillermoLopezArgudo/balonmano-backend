from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo, get_equipo_admin
from app.database import get_db

router = APIRouter(prefix="/temporadas", tags=["temporadas"])

PENDIENTES = ("programado", "aplazado")


def _pendientes(db: Session, id_temporada, id_equipo=None) -> int:
    q = db.query(models.Partido).filter(
        models.Partido.id_temporada == id_temporada,
        models.Partido.estado.in_(PENDIENTES),
    )
    if id_equipo is not None:
        from sqlalchemy import or_

        q = q.filter(
            or_(
                models.Partido.id_equipo == id_equipo,
                models.Partido.id_equipo_local == id_equipo,
                models.Partido.id_equipo_visitante == id_equipo,
            )
        )
    return q.count()


def _out(db: Session, t: models.Temporada, id_equipo=None) -> schemas.TemporadaOut:
    return schemas.TemporadaOut(
        id_temporada=t.id_temporada,
        nombre=t.nombre,
        fecha_inicio=t.fecha_inicio,
        fecha_fin=t.fecha_fin,
        estado=t.estado or "activa",
        cerrada_en=t.cerrada_en,
        pendientes=_pendientes(db, t.id_temporada, id_equipo),
    )


def _temporadas_club(db: Session, id_equipo):
    return (
        db.query(models.Temporada)
        .filter(models.Temporada.id_equipo == id_equipo)
        .order_by(models.Temporada.fecha_inicio.desc())
        .all()
    )


def _get_owned(db: Session, id_temporada, id_equipo) -> models.Temporada | None:
    return (
        db.query(models.Temporada)
        .filter(
            models.Temporada.id_temporada == id_temporada,
            models.Temporada.id_equipo == id_equipo,
        )
        .first()
    )


def _cerrar_activas_club(db: Session, id_equipo, except_id=None) -> None:
    q = db.query(models.Temporada).filter(
        models.Temporada.id_equipo == id_equipo,
        models.Temporada.estado == "activa",
    )
    if except_id is not None:
        q = q.filter(models.Temporada.id_temporada != except_id)
    for t in q.all():
        t.estado = "cerrada"
        t.cerrada_en = datetime.utcnow()


@router.get("/", response_model=list[schemas.TemporadaOut])
def listar(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    rows = _temporadas_club(db, equipo.id_equipo)
    return [_out(db, t, equipo.id_equipo) for t in rows]


@router.get("/activa", response_model=schemas.TemporadaOut | None)
def activa(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    t = (
        db.query(models.Temporada)
        .filter(
            models.Temporada.id_equipo == equipo.id_equipo,
            models.Temporada.estado == "activa",
        )
        .order_by(models.Temporada.fecha_inicio.desc())
        .first()
    )
    return _out(db, t, equipo.id_equipo) if t else None


@router.post("/", response_model=schemas.TemporadaOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: schemas.TemporadaCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    if payload.fecha_fin < payload.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin debe ser >= fecha_inicio")
    data = payload.model_dump(exclude={"activar"})
    temporada = models.Temporada(
        **data,
        id_equipo=equipo.id_equipo,
        estado="activa" if payload.activar else "cerrada",
    )
    if payload.activar:
        _cerrar_activas_club(db, equipo.id_equipo)
        temporada.estado = "activa"
        temporada.cerrada_en = None
    db.add(temporada)
    db.flush()
    db.add(
        models.EquipoTemporada(
            id_equipo=equipo.id_equipo,
            id_temporada=temporada.id_temporada,
        )
    )
    db.commit()
    db.refresh(temporada)
    return _out(db, temporada, equipo.id_equipo)


@router.post("/abrir", response_model=schemas.TemporadaOut, status_code=status.HTTP_201_CREATED)
def abrir(
    payload: schemas.TemporadaAbrir,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    if payload.fecha_fin < payload.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin debe ser >= fecha_inicio")
    if payload.cerrar_anterior:
        _cerrar_activas_club(db, equipo.id_equipo)
    misma = (
        db.query(models.Temporada)
        .filter(
            models.Temporada.id_equipo == equipo.id_equipo,
            models.Temporada.nombre == payload.nombre.strip(),
        )
        .first()
    )
    if misma:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una temporada «{payload.nombre}». Reactívala o elige otro nombre.",
        )
    temporada = models.Temporada(
        id_equipo=equipo.id_equipo,
        nombre=payload.nombre,
        fecha_inicio=payload.fecha_inicio,
        fecha_fin=payload.fecha_fin,
        estado="activa",
        cerrada_en=None,
    )
    db.add(temporada)
    db.flush()
    db.add(
        models.EquipoTemporada(
            id_equipo=equipo.id_equipo,
            id_temporada=temporada.id_temporada,
        )
    )
    db.commit()
    db.refresh(temporada)
    return _out(db, temporada, equipo.id_equipo)


@router.post("/{id_temporada}/cerrar", response_model=schemas.TemporadaOut)
def cerrar(
    id_temporada: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    t = _get_owned(db, id_temporada, equipo.id_equipo)
    if not t:
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    if t.estado == "archivada":
        raise HTTPException(status_code=400, detail="La temporada ya está archivada")
    t.estado = "cerrada"
    t.cerrada_en = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return _out(db, t, equipo.id_equipo)


@router.post("/{id_temporada}/activar", response_model=schemas.TemporadaOut)
def activar(
    id_temporada: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    t = _get_owned(db, id_temporada, equipo.id_equipo)
    if not t:
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    if t.estado == "archivada":
        raise HTTPException(status_code=400, detail="No se puede reactivar una archivada")
    _cerrar_activas_club(db, equipo.id_equipo, except_id=t.id_temporada)
    t.estado = "activa"
    t.cerrada_en = None
    db.commit()
    db.refresh(t)
    return _out(db, t, equipo.id_equipo)


@router.post("/{id_temporada}/archivar", response_model=schemas.TemporadaOut)
def archivar(
    id_temporada: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    t = _get_owned(db, id_temporada, equipo.id_equipo)
    if not t:
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    if t.estado == "activa":
        raise HTTPException(status_code=400, detail="Cierra la temporada antes de archivarla")
    pendientes = _pendientes(db, t.id_temporada, equipo.id_equipo)
    if pendientes:
        raise HTTPException(
            status_code=400,
            detail=f"Quedan {pendientes} partido(s) pendientes (aplazados/programados)",
        )
    t.estado = "archivada"
    if not t.cerrada_en:
        t.cerrada_en = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return _out(db, t, equipo.id_equipo)


@router.delete("/{id_temporada}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    id_temporada: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    temporada = _get_owned(db, id_temporada, equipo.id_equipo)
    if not temporada:
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    if temporada.estado == "activa":
        raise HTTPException(status_code=400, detail="No se puede borrar la temporada activa")

    # Borrar partidos primero: SQLAlchemy intenta poner id_temporada=NULL y falla (NOT NULL)
    partidos = (
        db.query(models.Partido)
        .filter(models.Partido.id_temporada == temporada.id_temporada)
        .all()
    )
    for p in partidos:
        db.delete(p)
    db.flush()

    db.delete(temporada)
    db.commit()
