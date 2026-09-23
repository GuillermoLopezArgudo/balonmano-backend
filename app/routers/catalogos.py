from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["catalogos"])


@router.get("/posiciones/", response_model=list[schemas.PosicionOut])
def listar_posiciones(db: Session = Depends(get_db)):
    return db.query(models.Posicion).order_by(models.Posicion.id_posicion).all()


@router.get("/tipos-accion/", response_model=list[schemas.TipoAccionOut])
def listar_tipos_accion(db: Session = Depends(get_db)):
    return db.query(models.TipoAccion).order_by(models.TipoAccion.id_tipo_accion).all()
