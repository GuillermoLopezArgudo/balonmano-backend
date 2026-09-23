from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo
from app.database import get_db

router = APIRouter(prefix="/equipos", tags=["equipos"])


@router.get("/me", response_model=schemas.EquipoOut)
def mi_equipo(equipo: models.Equipo = Depends(get_current_equipo)):
    return equipo


@router.get("/{id_equipo}", response_model=schemas.EquipoOut)
def detalle(
    id_equipo: str,
    db: Session = Depends(get_db),
    actual: models.Equipo = Depends(get_current_equipo),
):
    if str(actual.id_equipo) != str(id_equipo):
        raise HTTPException(status_code=403, detail="No autorizado")
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == id_equipo)
        .first()
    )
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo
