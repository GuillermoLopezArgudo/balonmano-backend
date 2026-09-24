from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/alineaciones", tags=["alineaciones"])

ZONAS_VALIDAS = {
    "portero",
    "extremo_izq",
    "lateral_izq",
    "central",
    "lateral_der",
    "extremo_der",
    "pivote",
}


def _dorsal(jugador: models.Jugador, id_equipo) -> int | None:
    for je in jugador.equipos or []:
        if je.id_equipo == id_equipo:
            return je.dorsal
    return None


def _item_out(item: models.AlineacionPlantillaItem, id_equipo) -> schemas.AlineacionItemOut:
    j = item.jugador
    return schemas.AlineacionItemOut(
        id_jugador=item.id_jugador,
        zona_campo=item.zona_campo,
        nombre=j.nombre if j else None,
        apellido=j.apellido if j else None,
        dorsal=_dorsal(j, id_equipo) if j else None,
        posiciones=[jp.posicion.nombre for jp in (j.posiciones or []) if jp.posicion] if j else [],
    )


def _plantilla_out(p: models.AlineacionPlantilla, id_equipo) -> schemas.AlineacionOut:
    return schemas.AlineacionOut(
        id_alineacion=p.id_alineacion,
        nombre=p.nombre,
        tipo=p.tipo or "ataque",
        creado_en=p.creado_en,
        actualizado_en=p.actualizado_en,
        items=[_item_out(i, id_equipo) for i in (p.items or [])],
    )


def _load_plantilla(db: Session, id_alineacion, id_equipo) -> models.AlineacionPlantilla | None:
    return (
        db.query(models.AlineacionPlantilla)
        .options(
            joinedload(models.AlineacionPlantilla.items)
            .joinedload(models.AlineacionPlantillaItem.jugador)
            .joinedload(models.Jugador.posiciones)
            .joinedload(models.JugadorPosicion.posicion),
            joinedload(models.AlineacionPlantilla.items)
            .joinedload(models.AlineacionPlantillaItem.jugador)
            .joinedload(models.Jugador.equipos),
        )
        .filter(
            models.AlineacionPlantilla.id_alineacion == id_alineacion,
            models.AlineacionPlantilla.id_equipo == id_equipo,
        )
        .first()
    )


def _validar_items(
    db: Session,
    items: list[schemas.AlineacionItemIn],
    id_equipo,
    tipo: str = "ataque",
) -> None:
    max_pos = 6 if tipo == "ataque" else 7
    if len(items) > max_pos:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {max_pos} posiciones en la alineación de {tipo}",
        )
    zonas = [i.zona_campo for i in items]
    if len(zonas) != len(set(zonas)):
        raise HTTPException(status_code=400, detail="Zona de campo duplicada")
    ids = [i.id_jugador for i in items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Jugador duplicado en la alineación")
    for item in items:
        if item.zona_campo not in ZONAS_VALIDAS:
            raise HTTPException(status_code=400, detail=f"Zona inválida: {item.zona_campo}")
        if tipo == "ataque" and item.zona_campo == "portero":
            raise HTTPException(
                status_code=400,
                detail="La alineación de ataque no admite portera",
            )
        vinculo = (
            db.query(models.JugadorEquipo)
            .filter(
                models.JugadorEquipo.id_jugador == item.id_jugador,
                models.JugadorEquipo.id_equipo == id_equipo,
            )
            .first()
        )
        if not vinculo:
            raise HTTPException(
                status_code=400,
                detail="Hay jugadores que no pertenecen a tu equipo",
            )


@router.get("/", response_model=list[schemas.AlineacionOut])
def listar(
    tipo: str | None = None,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    q = (
        db.query(models.AlineacionPlantilla)
        .options(
            joinedload(models.AlineacionPlantilla.items)
            .joinedload(models.AlineacionPlantillaItem.jugador)
            .joinedload(models.Jugador.posiciones)
            .joinedload(models.JugadorPosicion.posicion),
            joinedload(models.AlineacionPlantilla.items)
            .joinedload(models.AlineacionPlantillaItem.jugador)
            .joinedload(models.Jugador.equipos),
        )
        .filter(models.AlineacionPlantilla.id_equipo == equipo.id_equipo)
    )
    if tipo in ("ataque", "defensa"):
        q = q.filter(models.AlineacionPlantilla.tipo == tipo)
    filas = q.order_by(models.AlineacionPlantilla.actualizado_en.desc()).all()
    return [_plantilla_out(p, equipo.id_equipo) for p in filas]


@router.post("/", response_model=schemas.AlineacionOut, status_code=201)
def crear(
    payload: schemas.AlineacionCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("convocatoria")),
):
    _validar_items(db, payload.items, equipo.id_equipo, payload.tipo)
    plantilla = models.AlineacionPlantilla(
        id_equipo=equipo.id_equipo,
        nombre=payload.nombre.strip(),
        tipo=payload.tipo,
    )
    db.add(plantilla)
    db.flush()
    for item in payload.items:
        db.add(
            models.AlineacionPlantillaItem(
                id_alineacion=plantilla.id_alineacion,
                id_jugador=item.id_jugador,
                zona_campo=item.zona_campo,
            )
        )
    db.commit()
    loaded = _load_plantilla(db, plantilla.id_alineacion, equipo.id_equipo)
    return _plantilla_out(loaded, equipo.id_equipo)


@router.put("/{id_alineacion}", response_model=schemas.AlineacionOut)
def actualizar(
    id_alineacion: str,
    payload: schemas.AlineacionUpdate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("convocatoria")),
):
    plantilla = _load_plantilla(db, id_alineacion, equipo.id_equipo)
    if not plantilla:
        raise HTTPException(status_code=404, detail="Alineación no encontrada")

    if payload.nombre is not None:
        plantilla.nombre = payload.nombre.strip()
    if payload.tipo is not None:
        plantilla.tipo = payload.tipo

    if payload.items is not None:
        tipo = payload.tipo or plantilla.tipo or "ataque"
        _validar_items(db, payload.items, equipo.id_equipo, tipo)
        plantilla.items.clear()
        db.flush()
        for item in payload.items:
            db.add(
                models.AlineacionPlantillaItem(
                    id_alineacion=plantilla.id_alineacion,
                    id_jugador=item.id_jugador,
                    zona_campo=item.zona_campo,
                )
            )

    db.commit()
    loaded = _load_plantilla(db, plantilla.id_alineacion, equipo.id_equipo)
    return _plantilla_out(loaded, equipo.id_equipo)


@router.delete("/{id_alineacion}", status_code=204)
def eliminar(
    id_alineacion: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("convocatoria")),
):
    plantilla = (
        db.query(models.AlineacionPlantilla)
        .filter(
            models.AlineacionPlantilla.id_alineacion == id_alineacion,
            models.AlineacionPlantilla.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not plantilla:
        raise HTTPException(status_code=404, detail="Alineación no encontrada")
    db.delete(plantilla)
    db.commit()
    return None
