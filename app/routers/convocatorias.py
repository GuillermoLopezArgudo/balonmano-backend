from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo
from app.database import get_db

router = APIRouter(prefix="/convocatorias", tags=["convocatorias"])

MAX_CONVOCADOS = 16
MAX_TITULARES = 7


def _partido_del_equipo(db: Session, id_partido: str, id_equipo) -> models.Partido | None:
    return partido_del_equipo(db, id_partido, id_equipo)


def _items_out(db: Session, id_partido, id_equipo) -> list[schemas.ConvocatoriaItemOut]:
    filas = (
        db.query(models.Convocatoria)
        .options(
            joinedload(models.Convocatoria.jugador)
            .joinedload(models.Jugador.posiciones)
            .joinedload(models.JugadorPosicion.posicion),
            joinedload(models.Convocatoria.jugador)
            .joinedload(models.Jugador.equipos),
        )
        .filter(models.Convocatoria.id_partido == id_partido)
        .all()
    )
    out = []
    for f in filas:
        j = f.jugador
        dorsal = None
        for je in j.equipos or []:
            if je.id_equipo == id_equipo:
                dorsal = je.dorsal
                break
        out.append(
            schemas.ConvocatoriaItemOut(
                id_jugador=f.id_jugador,
                rol=f.rol,
                nombre=j.nombre if j else None,
                apellido=j.apellido if j else None,
                dorsal=dorsal,
                posiciones=[jp.posicion.nombre for jp in (j.posiciones or []) if jp.posicion]
                if j
                else [],
            )
        )
    return out


@router.get("/partido/{id_partido}", response_model=schemas.ConvocatoriaOut)
def obtener(
    id_partido: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    partido = _partido_del_equipo(db, id_partido, equipo.id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return schemas.ConvocatoriaOut(
        id_partido=partido.id_partido,
        items=_items_out(db, partido.id_partido, equipo.id_equipo),
        confirmada=False,
    )


@router.put("/partido/{id_partido}", response_model=schemas.ConvocatoriaOut)
def guardar(
    id_partido: str,
    payload: schemas.ConvocatoriaPut,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    partido = _partido_del_equipo(db, id_partido, equipo.id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    if len(payload.items) > MAX_CONVOCADOS:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_CONVOCADOS} convocados",
        )
    titulares = [i for i in payload.items if i.rol == "titular"]
    if len(titulares) > MAX_TITULARES:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_TITULARES} titulares",
        )

    ids = [i.id_jugador for i in payload.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Jugador duplicado en la convocatoria")

    for item in payload.items:
        vinculo = (
            db.query(models.JugadorEquipo)
            .filter(
                models.JugadorEquipo.id_jugador == item.id_jugador,
                models.JugadorEquipo.id_equipo == equipo.id_equipo,
            )
            .first()
        )
        if not vinculo:
            raise HTTPException(
                status_code=400,
                detail="Hay jugadores que no pertenecen a tu equipo",
            )

    db.query(models.Convocatoria).filter(models.Convocatoria.id_partido == id_partido).delete()
    for item in payload.items:
        db.add(
            models.Convocatoria(
                id_partido=partido.id_partido,
                id_jugador=item.id_jugador,
                rol=item.rol,
            )
        )
    db.commit()

    return schemas.ConvocatoriaOut(
        id_partido=partido.id_partido,
        items=_items_out(db, partido.id_partido, equipo.id_equipo),
        confirmada=payload.confirmada,
    )
