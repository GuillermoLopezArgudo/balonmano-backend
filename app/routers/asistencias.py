from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import AuthSession, get_current_equipo, get_current_session
from app.database import get_db
from app.permisos import AREA_LABELS

router = APIRouter(prefix="/asistencias", tags=["asistencias"])

try:
    from zoneinfo import ZoneInfo

    _TZ_CLUB = ZoneInfo("Europe/Madrid")
except Exception:  # pragma: no cover
    _TZ_CLUB = None


def _assert_write(session: AuthSession) -> None:
    if not session.can_write_area("fisico"):
        label = AREA_LABELS.get("fisico", "fisico")
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede modificar {label}",
        )


def _dia_club(dt: datetime) -> date:
    """Día civil del club (Europe/Madrid): un entrenamiento = una asistencia al día."""
    if dt.tzinfo is None:
        if _TZ_CLUB is not None:
            dt = dt.replace(tzinfo=_TZ_CLUB)
        return dt.date()
    if _TZ_CLUB is not None:
        return dt.astimezone(_TZ_CLUB).date()
    return dt.date()


def _assert_unica_por_dia(
    db: Session,
    id_equipo,
    fecha: datetime,
    *,
    exclude_id=None,
) -> None:
    dia = _dia_club(fecha)
    filas = (
        db.query(models.SesionEntrenamiento)
        .filter(models.SesionEntrenamiento.id_equipo == id_equipo)
        .all()
    )
    for s in filas:
        if exclude_id is not None and s.id_sesion == exclude_id:
            continue
        if _dia_club(s.fecha) == dia:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Ya hay una sesión de asistencia el {dia.strftime('%d/%m/%Y')}. "
                    "Solo se permite un entrenamiento al día."
                ),
            )


def _get_sesion(db: Session, id_sesion, id_equipo) -> models.SesionEntrenamiento | None:
    return (
        db.query(models.SesionEntrenamiento)
        .filter(
            models.SesionEntrenamiento.id_sesion == id_sesion,
            models.SesionEntrenamiento.id_equipo == id_equipo,
        )
        .first()
    )


def _counts(db: Session, id_sesion) -> tuple[int, int, int, int]:
    rows = (
        db.query(models.SesionAsistencia.estado, func.count())
        .filter(models.SesionAsistencia.id_sesion == id_sesion)
        .group_by(models.SesionAsistencia.estado)
        .all()
    )
    m = {estado: int(n) for estado, n in rows}
    presentes = m.get("presente", 0)
    faltas = m.get("falta", 0)
    justificadas = m.get("justificada", 0)
    return presentes, faltas, justificadas, presentes + faltas + justificadas


def _detalle(db: Session, sesion: models.SesionEntrenamiento, id_equipo) -> schemas.SesionEntrenamientoDetalleOut:
    plantilla = (
        db.query(models.Jugador, models.JugadorEquipo.dorsal)
        .join(models.JugadorEquipo, models.JugadorEquipo.id_jugador == models.Jugador.id_jugador)
        .filter(
            models.JugadorEquipo.id_equipo == id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
        )
        .order_by(models.JugadorEquipo.dorsal.asc(), models.Jugador.apellido, models.Jugador.nombre)
        .all()
    )
    marcados = {
        a.id_jugador: a.estado
        for a in db.query(models.SesionAsistencia)
        .filter(models.SesionAsistencia.id_sesion == sesion.id_sesion)
        .all()
    }
    items = []
    presentes = faltas = justificadas = 0
    for jugador, dorsal in plantilla:
        estado = marcados.get(jugador.id_jugador)
        if estado == "presente":
            presentes += 1
        elif estado == "falta":
            faltas += 1
        elif estado == "justificada":
            justificadas += 1
        items.append(
            schemas.SesionAsistenciaItemOut(
                id_jugador=jugador.id_jugador,
                nombre=jugador.nombre,
                apellido=jugador.apellido,
                dorsal=dorsal,
                estado=estado,
            )
        )
    return schemas.SesionEntrenamientoDetalleOut(
        id_sesion=sesion.id_sesion,
        fecha=sesion.fecha,
        notas=sesion.notas,
        items=items,
        presentes=presentes,
        faltas=faltas,
        justificadas=justificadas,
    )


@router.get("/", response_model=list[schemas.SesionEntrenamientoListOut])
def listar(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    filas = (
        db.query(models.SesionEntrenamiento)
        .filter(models.SesionEntrenamiento.id_equipo == equipo.id_equipo)
        .order_by(models.SesionEntrenamiento.fecha.desc())
        .all()
    )
    out = []
    for s in filas:
        presentes, faltas, justificadas, marcadas = _counts(db, s.id_sesion)
        out.append(
            schemas.SesionEntrenamientoListOut(
                id_sesion=s.id_sesion,
                fecha=s.fecha,
                notas=s.notas,
                presentes=presentes,
                faltas=faltas,
                justificadas=justificadas,
                marcadas=marcadas,
            )
        )
    return out


@router.post("/", response_model=schemas.SesionEntrenamientoDetalleOut, status_code=201)
def crear(
    payload: schemas.SesionEntrenamientoCreate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    _assert_write(session)
    equipo = session.equipo
    _assert_unica_por_dia(db, equipo.id_equipo, payload.fecha)
    notas = (payload.notas or "").strip() or None
    sesion = models.SesionEntrenamiento(
        id_equipo=equipo.id_equipo,
        fecha=payload.fecha,
        notas=notas,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return _detalle(db, sesion, equipo.id_equipo)


@router.get("/{id_sesion}", response_model=schemas.SesionEntrenamientoDetalleOut)
def obtener(
    id_sesion: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    sesion = _get_sesion(db, id_sesion, equipo.id_equipo)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return _detalle(db, sesion, equipo.id_equipo)


@router.put("/{id_sesion}", response_model=schemas.SesionEntrenamientoDetalleOut)
def actualizar(
    id_sesion: str,
    payload: schemas.SesionEntrenamientoUpdate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    _assert_write(session)
    equipo = session.equipo
    sesion = _get_sesion(db, id_sesion, equipo.id_equipo)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "fecha" in data and data["fecha"] is not None:
        _assert_unica_por_dia(
            db, equipo.id_equipo, data["fecha"], exclude_id=sesion.id_sesion
        )
        sesion.fecha = data["fecha"]
    if "notas" in data:
        raw = data["notas"]
        sesion.notas = (raw or "").strip() or None
    db.commit()
    db.refresh(sesion)
    return _detalle(db, sesion, equipo.id_equipo)


@router.put("/{id_sesion}/marcajes", response_model=schemas.SesionEntrenamientoDetalleOut)
def guardar_marcajes(
    id_sesion: str,
    payload: schemas.SesionAsistenciaPutIn,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    _assert_write(session)
    equipo = session.equipo
    sesion = _get_sesion(db, id_sesion, equipo.id_equipo)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    activos = {
        r[0]
        for r in db.query(models.JugadorEquipo.id_jugador)
        .filter(
            models.JugadorEquipo.id_equipo == equipo.id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
        )
        .all()
    }
    db.query(models.SesionAsistencia).filter(
        models.SesionAsistencia.id_sesion == sesion.id_sesion
    ).delete()
    for item in payload.items:
        if item.id_jugador not in activos:
            continue
        db.add(
            models.SesionAsistencia(
                id_sesion=sesion.id_sesion,
                id_jugador=item.id_jugador,
                estado=item.estado,
            )
        )
    db.commit()
    return _detalle(db, sesion, equipo.id_equipo)


@router.delete("/{id_sesion}", status_code=204)
def eliminar(
    id_sesion: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    _assert_write(session)
    sesion = _get_sesion(db, id_sesion, session.equipo.id_equipo)
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    db.delete(sesion)
    db.commit()
    return None
