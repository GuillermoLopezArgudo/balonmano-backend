from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo
from app.database import get_db

router = APIRouter(prefix="/miembros", tags=["miembros"])


def _nombre_desde_correo(correo: str) -> str:
    local = (correo or "usuario").split("@")[0]
    return local.replace(".", " ").replace("_", " ").title() or "Usuario"


def _ensure_owner(db: Session, equipo: models.Equipo) -> None:
    exists = (
        db.query(models.MiembroClub)
        .filter(models.MiembroClub.id_equipo == equipo.id_equipo)
        .count()
    )
    if exists:
        return
    nombre = None
    if equipo.datos and equipo.datos.entrenador_nombre:
        nombre = equipo.datos.entrenador_nombre
    if not nombre:
        nombre = _nombre_desde_correo(equipo.correo)
    owner = models.MiembroClub(
        id_equipo=equipo.id_equipo,
        nombre=nombre,
        correo=equipo.correo,
        cargo="Entrenador principal",
        permiso="administrador",
        estado="activo",
    )
    db.add(owner)
    db.commit()


def _out(m: models.MiembroClub) -> schemas.MiembroOut:
    return schemas.MiembroOut.model_validate(m)


@router.get("/", response_model=list[schemas.MiembroOut])
def list_miembros(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _ensure_owner(db, equipo)
    rows = (
        db.query(models.MiembroClub)
        .filter(models.MiembroClub.id_equipo == equipo.id_equipo)
        .order_by(models.MiembroClub.creado_en.asc())
        .all()
    )
    return [_out(r) for r in rows]


@router.post("/", response_model=schemas.MiembroOut, status_code=201)
def invite_miembro(
    payload: schemas.MiembroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _ensure_owner(db, equipo)
    correo = payload.correo.strip().lower()
    row = models.MiembroClub(
        id_equipo=equipo.id_equipo,
        nombre=payload.nombre.strip(),
        correo=correo,
        cargo=payload.cargo.strip() or "Staff",
        permiso=payload.permiso,
        estado=payload.estado,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un miembro con ese correo")
    db.refresh(row)
    return _out(row)


@router.patch("/{id_miembro}", response_model=schemas.MiembroOut)
def update_miembro(
    id_miembro: str,
    payload: schemas.MiembroUpdate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    row = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip()
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{id_miembro}", status_code=204)
def delete_miembro(
    id_miembro: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    row = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if row.correo.lower() == (equipo.correo or "").lower() and row.permiso == "administrador":
        raise HTTPException(status_code=400, detail="No puedes eliminar al administrador principal")
    db.delete(row)
    db.commit()
    return None
