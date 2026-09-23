from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo
from app.database import get_db

router = APIRouter(prefix="/rivales", tags=["rivales"])


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
    equipo: models.Equipo = Depends(get_current_equipo),
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
def borrar(
    id_rival: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    rival = (
        db.query(models.Rival)
        .filter(models.Rival.id_rival == id_rival, models.Rival.id_equipo == equipo.id_equipo)
        .first()
    )
    if not rival:
        raise HTTPException(status_code=404, detail="Rival no encontrado")
    usados = db.query(models.Partido).filter(models.Partido.id_rival == id_rival).count()
    if usados:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar: tiene {usados} partido(s) asociados",
        )
    db.delete(rival)
    db.commit()
