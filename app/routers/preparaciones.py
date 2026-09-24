from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/preparaciones", tags=["preparaciones"])

TIPOS_VALIDOS = {
    "fuerza",
    "resistencia",
    "potencia",
    "movilidad",
    "prevencion",
    "prepartido",
    "recuperacion",
    "otro",
}


def _out(p: models.PreparacionFisica) -> schemas.PreparacionFisicaOut:
    return schemas.PreparacionFisicaOut(
        id_preparacion=p.id_preparacion,
        nombre=p.nombre,
        tipo=p.tipo,
        objetivo=p.objetivo,
        contenido=p.contenido,
        duracion_min=p.duracion_min,
        intensidad=p.intensidad,
        creado_en=p.creado_en,
        actualizado_en=p.actualizado_en,
    )


def _get(db: Session, id_preparacion, id_equipo) -> models.PreparacionFisica | None:
    return (
        db.query(models.PreparacionFisica)
        .filter(
            models.PreparacionFisica.id_preparacion == id_preparacion,
            models.PreparacionFisica.id_equipo == id_equipo,
        )
        .first()
    )


@router.get("/", response_model=list[schemas.PreparacionFisicaOut])
def listar(
    tipo: str | None = None,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    q = db.query(models.PreparacionFisica).filter(
        models.PreparacionFisica.id_equipo == equipo.id_equipo
    )
    if tipo in TIPOS_VALIDOS:
        q = q.filter(models.PreparacionFisica.tipo == tipo)
    filas = q.order_by(models.PreparacionFisica.actualizado_en.desc()).all()
    return [_out(p) for p in filas]


@router.get("/{id_preparacion}", response_model=schemas.PreparacionFisicaOut)
def obtener(
    id_preparacion: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    p = _get(db, id_preparacion, equipo.id_equipo)
    if not p:
        raise HTTPException(status_code=404, detail="Preparación no encontrada")
    return _out(p)


@router.post("/", response_model=schemas.PreparacionFisicaOut, status_code=201)
def crear(
    payload: schemas.PreparacionFisicaCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("fisico")),
):
    p = models.PreparacionFisica(
        id_equipo=equipo.id_equipo,
        nombre=payload.nombre.strip(),
        tipo=payload.tipo,
        objetivo=(payload.objetivo or "").strip() or None,
        contenido=(payload.contenido or "").strip() or None,
        duracion_min=payload.duracion_min,
        intensidad=payload.intensidad,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.put("/{id_preparacion}", response_model=schemas.PreparacionFisicaOut)
def actualizar(
    id_preparacion: str,
    payload: schemas.PreparacionFisicaUpdate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("fisico")),
):
    p = _get(db, id_preparacion, equipo.id_equipo)
    if not p:
        raise HTTPException(status_code=404, detail="Preparación no encontrada")

    data = payload.model_dump(exclude_unset=True)
    if "nombre" in data and data["nombre"] is not None:
        p.nombre = data["nombre"].strip()
    if "tipo" in data and data["tipo"] is not None:
        p.tipo = data["tipo"]
    if "objetivo" in data:
        raw = data["objetivo"]
        p.objetivo = (raw or "").strip() or None
    if "contenido" in data:
        raw = data["contenido"]
        p.contenido = (raw or "").strip() or None
    if "duracion_min" in data:
        p.duracion_min = data["duracion_min"]
    if "intensidad" in data:
        p.intensidad = data["intensidad"]

    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{id_preparacion}", status_code=204)
def eliminar(
    id_preparacion: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("fisico")),
):
    p = _get(db, id_preparacion, equipo.id_equipo)
    if not p:
        raise HTTPException(status_code=404, detail="Preparación no encontrada")
    db.delete(p)
    db.commit()
    return None
