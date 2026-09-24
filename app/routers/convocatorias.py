from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo, get_equipo_area
from app.database import get_db
from app.routers.cuotas import federacion_pagada

router = APIRouter(prefix="/convocatorias", tags=["convocatorias"])

MAX_CONVOCADOS = 16
MAX_TITULARES = 7
ZONAS_VALIDAS = {
    "portero",
    "extremo_izq",
    "lateral_izq",
    "central",
    "lateral_der",
    "extremo_der",
    "pivote",
}


def _partido_del_equipo(db: Session, id_partido: str, id_equipo) -> models.Partido | None:
    return partido_del_equipo(db, id_partido, id_equipo)


def _norm_zona(z: str | None) -> str | None:
    return z if z in ZONAS_VALIDAS else None


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
        zona_ataque = f.zona_ataque or f.zona_campo
        zona_defensa = f.zona_defensa
        out.append(
            schemas.ConvocatoriaItemOut(
                id_jugador=f.id_jugador,
                rol=f.rol,
                zona_campo=zona_ataque,
                zona_ataque=zona_ataque,
                zona_defensa=zona_defensa,
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
    equipo: models.Equipo = Depends(get_equipo_area("convocatoria")),
):
    partido = _partido_del_equipo(db, id_partido, equipo.id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    if len(payload.items) > MAX_CONVOCADOS:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_CONVOCADOS} convocados",
        )

    id_temporada = partido.id_temporada
    sin_fed = []

    ids = [i.id_jugador for i in payload.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Jugador duplicado en la convocatoria")

    zonas_ataque = []
    zonas_defensa = []
    for item in payload.items:
        za = _norm_zona(item.zona_ataque or item.zona_campo)
        zd = _norm_zona(item.zona_defensa)
        if item.zona_ataque and item.zona_ataque not in ZONAS_VALIDAS:
            raise HTTPException(status_code=400, detail=f"Zona ataque inválida: {item.zona_ataque}")
        if item.zona_campo and item.zona_campo not in ZONAS_VALIDAS and not item.zona_ataque:
            raise HTTPException(status_code=400, detail=f"Zona inválida: {item.zona_campo}")
        if item.zona_defensa and item.zona_defensa not in ZONAS_VALIDAS:
            raise HTTPException(status_code=400, detail=f"Zona defensa inválida: {item.zona_defensa}")
        if za:
            zonas_ataque.append(za)
        if zd:
            zonas_defensa.append(zd)

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

        if id_temporada and not federacion_pagada(
            db, equipo.id_equipo, id_temporada, item.id_jugador
        ):
            j = db.get(models.Jugador, item.id_jugador)
            nombre = f"{j.nombre} {j.apellido}".strip() if j else str(item.id_jugador)
            sin_fed.append(nombre)

    if sin_fed:
        lista = ", ".join(sin_fed[:5])
        extra = f" (+{len(sin_fed) - 5} más)" if len(sin_fed) > 5 else ""
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede convocar sin federación pagada: {lista}{extra}. "
                "Márcala en Club → Cuotas."
            ),
        )

    if len(zonas_ataque) != len(set(zonas_ataque)):
        raise HTTPException(status_code=400, detail="Zona de ataque duplicada")
    if len(zonas_defensa) != len(set(zonas_defensa)):
        raise HTTPException(status_code=400, detail="Zona de defensa duplicada")
    if len(zonas_ataque) > MAX_TITULARES - 1:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_TITULARES - 1} en alineación de ataque (sin portera)",
        )
    if "portero" in zonas_ataque:
        raise HTTPException(
            status_code=400,
            detail="La alineación de ataque no admite portera",
        )
    if len(zonas_defensa) > MAX_TITULARES:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_TITULARES} en alineación de defensa")

    db.query(models.Convocatoria).filter(models.Convocatoria.id_partido == id_partido).delete()
    for item in payload.items:
        za = _norm_zona(item.zona_ataque or item.zona_campo)
        zd = _norm_zona(item.zona_defensa)
        # Titular si está en alguna alineación de campo
        rol = item.rol
        if za or zd:
            rol = "titular"
        db.add(
            models.Convocatoria(
                id_partido=partido.id_partido,
                id_jugador=item.id_jugador,
                rol=rol,
                zona_campo=za,
                zona_ataque=za,
                zona_defensa=zd,
            )
        )
    db.commit()

    return schemas.ConvocatoriaOut(
        id_partido=partido.id_partido,
        items=_items_out(db, partido.id_partido, equipo.id_equipo),
        confirmada=payload.confirmada,
    )
