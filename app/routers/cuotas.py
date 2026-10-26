from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_equipo_area, get_equipo_area_read
from app.database import get_db

router = APIRouter(prefix="/cuotas", tags=["cuotas"])

MESES = list(schemas.CUOTA_MESES_ORDEN)
MES_LABELS = {
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
}


def _temporada_del_equipo(db: Session, id_temporada, id_equipo) -> models.Temporada | None:
    return (
        db.query(models.Temporada)
        .filter(
            models.Temporada.id_temporada == id_temporada,
            models.Temporada.id_equipo == id_equipo,
        )
        .first()
    )


def _resolve_temporada(
    db: Session, equipo: models.Equipo, id_temporada: str | None
) -> models.Temporada:
    if id_temporada:
        t = _temporada_del_equipo(db, id_temporada, equipo.id_equipo)
        if not t:
            raise HTTPException(status_code=404, detail="Temporada no encontrada")
        return t
    t = (
        db.query(models.Temporada)
        .filter(
            models.Temporada.id_equipo == equipo.id_equipo,
            models.Temporada.estado == "activa",
        )
        .order_by(models.Temporada.fecha_inicio.desc())
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="No hay temporada activa")
    return t


def _get_or_create_config(
    db: Session, id_equipo, id_temporada
) -> models.CuotaConfig:
    cfg = (
        db.query(models.CuotaConfig)
        .filter(
            models.CuotaConfig.id_equipo == id_equipo,
            models.CuotaConfig.id_temporada == id_temporada,
        )
        .first()
    )
    if cfg:
        return cfg
    cfg = models.CuotaConfig(
        id_equipo=id_equipo,
        id_temporada=id_temporada,
        importe_mensual=0.0,
        importe_federacion=0.0,
    )
    db.add(cfg)
    db.flush()
    return cfg


def _jugadoras_activas(db: Session, id_equipo) -> list[tuple[models.Jugador, int | None]]:
    filas = (
        db.query(models.Jugador, models.JugadorEquipo.dorsal)
        .join(models.JugadorEquipo, models.JugadorEquipo.id_jugador == models.Jugador.id_jugador)
        .filter(
            models.JugadorEquipo.id_equipo == id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
        )
        .order_by(models.JugadorEquipo.dorsal.asc(), models.Jugador.apellido)
        .all()
    )
    return [(j, dorsal) for j, dorsal in filas]


def _build_out(
    db: Session, equipo: models.Equipo, temporada: models.Temporada
) -> schemas.CuotasTemporadaOut:
    cfg = _get_or_create_config(db, equipo.id_equipo, temporada.id_temporada)
    jugadoras = _jugadoras_activas(db, equipo.id_equipo)
    ids = [j.id_jugador for j, _ in jugadoras]

    mensual_rows = (
        db.query(models.CuotaMensual)
        .filter(
            models.CuotaMensual.id_equipo == equipo.id_equipo,
            models.CuotaMensual.id_temporada == temporada.id_temporada,
            models.CuotaMensual.id_jugador.in_(ids) if ids else False,
        )
        .all()
        if ids
        else []
    )
    fed_rows = (
        db.query(models.FederacionPago)
        .filter(
            models.FederacionPago.id_equipo == equipo.id_equipo,
            models.FederacionPago.id_temporada == temporada.id_temporada,
            models.FederacionPago.id_jugador.in_(ids) if ids else False,
        )
        .all()
        if ids
        else []
    )

    mensual_map: dict[tuple, bool] = {
        (r.id_jugador, r.mes): bool(r.pagado) for r in mensual_rows
    }
    fed_map = {r.id_jugador: bool(r.pagado) for r in fed_rows}

    out_jugs: list[schemas.CuotaJugadoraOut] = []
    fed_ok = 0
    cuotas_ok = 0
    total_slots = len(jugadoras) * len(MESES)

    for j, dorsal in jugadoras:
        fed = fed_map.get(j.id_jugador, False)
        if fed:
            fed_ok += 1
        meses = []
        for m in MESES:
            pagado = mensual_map.get((j.id_jugador, m), False)
            if pagado:
                cuotas_ok += 1
            meses.append(schemas.CuotaMesEstado(mes=m, pagado=pagado))
        out_jugs.append(
            schemas.CuotaJugadoraOut(
                id_jugador=j.id_jugador,
                nombre=j.nombre,
                apellido=j.apellido,
                dorsal=dorsal,
                federacion_pagada=fed,
                meses=meses,
            )
        )

    n = len(jugadoras)
    imp_m = float(cfg.importe_mensual or 0)
    imp_f = float(cfg.importe_federacion or 0)

    resumen = schemas.CuotaResumenOut(
        total_jugadoras=n,
        federacion_pagadas=fed_ok,
        federacion_pendientes=n - fed_ok,
        cuotas_pagadas=cuotas_ok,
        cuotas_pendientes=max(0, total_slots - cuotas_ok),
        esperado_mensual=round(imp_m * total_slots, 2),
        cobrado_mensual=round(imp_m * cuotas_ok, 2),
        esperado_federacion=round(imp_f * n, 2),
        cobrado_federacion=round(imp_f * fed_ok, 2),
    )

    return schemas.CuotasTemporadaOut(
        id_temporada=temporada.id_temporada,
        temporada_nombre=temporada.nombre,
        temporada_estado=temporada.estado or "activa",
        meses=MESES,
        config=schemas.CuotaConfigOut(
            id_temporada=temporada.id_temporada,
            importe_mensual=imp_m,
            importe_federacion=imp_f,
        ),
        jugadoras=out_jugs,
        resumen=resumen,
        solo_lectura=(temporada.estado or "") in ("cerrada", "archivada"),
    )


def federacion_pagada(
    db: Session, id_equipo, id_temporada, id_jugador
) -> bool:
    row = (
        db.query(models.FederacionPago)
        .filter(
            models.FederacionPago.id_equipo == id_equipo,
            models.FederacionPago.id_temporada == id_temporada,
            models.FederacionPago.id_jugador == id_jugador,
            models.FederacionPago.pagado.is_(True),
        )
        .first()
    )
    return bool(row)


@router.get("/", response_model=schemas.CuotasTemporadaOut)
def obtener_cuotas(
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area_read("cuotas")),
):
    temporada = _resolve_temporada(db, equipo, id_temporada)
    out = _build_out(db, equipo, temporada)
    db.commit()
    return out


@router.put("/config", response_model=schemas.CuotasTemporadaOut)
def actualizar_config(
    payload: schemas.CuotaConfigIn,
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("cuotas")),
):
    temporada = _resolve_temporada(db, equipo, id_temporada)
    if temporada.estado in ("cerrada", "archivada"):
        raise HTTPException(
            status_code=400,
            detail="No se puede editar la configuración en temporada cerrada",
        )
    cfg = _get_or_create_config(db, equipo.id_equipo, temporada.id_temporada)
    cfg.importe_mensual = float(payload.importe_mensual)
    cfg.importe_federacion = float(payload.importe_federacion)
    db.commit()
    return _build_out(db, equipo, temporada)


@router.patch("/mensual", response_model=schemas.CuotasTemporadaOut)
def patch_mensual(
    payload: schemas.CuotaMensualPatch,
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("cuotas")),
):
    temporada = _resolve_temporada(db, equipo, id_temporada)
    if temporada.estado in ("cerrada", "archivada"):
        raise HTTPException(status_code=400, detail="Temporada cerrada: solo lectura")
    if payload.mes not in MESES:
        raise HTTPException(status_code=400, detail="Mes fuera del periodo Sep–Jun")

    vinculo = (
        db.query(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_jugador == payload.id_jugador,
            models.JugadorEquipo.id_equipo == equipo.id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
        )
        .first()
    )
    if not vinculo:
        raise HTTPException(status_code=400, detail="Jugadora no activa en el equipo")

    row = (
        db.query(models.CuotaMensual)
        .filter(
            models.CuotaMensual.id_equipo == equipo.id_equipo,
            models.CuotaMensual.id_temporada == temporada.id_temporada,
            models.CuotaMensual.id_jugador == payload.id_jugador,
            models.CuotaMensual.mes == payload.mes,
        )
        .first()
    )
    if not row:
        row = models.CuotaMensual(
            id_equipo=equipo.id_equipo,
            id_temporada=temporada.id_temporada,
            id_jugador=payload.id_jugador,
            mes=payload.mes,
        )
        db.add(row)
    row.pagado = bool(payload.pagado)
    row.pagado_en = datetime.utcnow() if payload.pagado else None
    db.commit()
    return _build_out(db, equipo, temporada)


@router.patch("/federacion", response_model=schemas.CuotasTemporadaOut)
def patch_federacion(
    payload: schemas.FederacionPatch,
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("cuotas")),
):
    temporada = _resolve_temporada(db, equipo, id_temporada)
    if temporada.estado in ("cerrada", "archivada"):
        raise HTTPException(status_code=400, detail="Temporada cerrada: solo lectura")

    vinculo = (
        db.query(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_jugador == payload.id_jugador,
            models.JugadorEquipo.id_equipo == equipo.id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
        )
        .first()
    )
    if not vinculo:
        raise HTTPException(status_code=400, detail="Jugadora no activa en el equipo")

    row = (
        db.query(models.FederacionPago)
        .filter(
            models.FederacionPago.id_equipo == equipo.id_equipo,
            models.FederacionPago.id_temporada == temporada.id_temporada,
            models.FederacionPago.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if not row:
        row = models.FederacionPago(
            id_equipo=equipo.id_equipo,
            id_temporada=temporada.id_temporada,
            id_jugador=payload.id_jugador,
        )
        db.add(row)
    row.pagado = bool(payload.pagado)
    row.pagado_en = datetime.utcnow() if payload.pagado else None
    db.commit()
    return _build_out(db, equipo, temporada)


@router.post("/bulk", response_model=schemas.CuotasTemporadaOut)
def bulk_cuotas(
    payload: schemas.CuotaBulkIn,
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("cuotas")),
):
    temporada = _resolve_temporada(db, equipo, id_temporada)
    if temporada.estado in ("cerrada", "archivada"):
        raise HTTPException(status_code=400, detail="Temporada cerrada: solo lectura")

    ids = list({jid for jid in payload.id_jugadores})
    activos = (
        db.query(models.JugadorEquipo.id_jugador)
        .filter(
            models.JugadorEquipo.id_equipo == equipo.id_equipo,
            models.JugadorEquipo.fecha_baja.is_(None),
            models.JugadorEquipo.id_jugador.in_(ids),
        )
        .all()
    )
    valid = {row[0] for row in activos}
    if not valid:
        raise HTTPException(status_code=400, detail="Ninguna jugadora válida en la selección")

    if payload.accion == "limpiar":
        db.query(models.CuotaMensual).filter(
            models.CuotaMensual.id_equipo == equipo.id_equipo,
            models.CuotaMensual.id_temporada == temporada.id_temporada,
            models.CuotaMensual.id_jugador.in_(valid),
        ).delete(synchronize_session=False)
        db.query(models.FederacionPago).filter(
            models.FederacionPago.id_equipo == equipo.id_equipo,
            models.FederacionPago.id_temporada == temporada.id_temporada,
            models.FederacionPago.id_jugador.in_(valid),
        ).delete(synchronize_session=False)
    elif payload.accion in ("cuotas_pagadas", "cuotas_pendientes"):
        pagado = payload.accion == "cuotas_pagadas"
        ahora = datetime.utcnow()
        existentes = (
            db.query(models.CuotaMensual)
            .filter(
                models.CuotaMensual.id_equipo == equipo.id_equipo,
                models.CuotaMensual.id_temporada == temporada.id_temporada,
                models.CuotaMensual.id_jugador.in_(valid),
            )
            .all()
        )
        por_clave = {(row.id_jugador, row.mes): row for row in existentes}
        for jid in valid:
            for mes in MESES:
                row = por_clave.get((jid, mes))
                if not row:
                    row = models.CuotaMensual(
                        id_equipo=equipo.id_equipo,
                        id_temporada=temporada.id_temporada,
                        id_jugador=jid,
                        mes=mes,
                    )
                    db.add(row)
                row.pagado = pagado
                row.pagado_en = ahora if pagado else None
    else:
        pagado = payload.accion == "federacion_pagada"
        for jid in valid:
            row = (
                db.query(models.FederacionPago)
                .filter(
                    models.FederacionPago.id_equipo == equipo.id_equipo,
                    models.FederacionPago.id_temporada == temporada.id_temporada,
                    models.FederacionPago.id_jugador == jid,
                )
                .first()
            )
            if not row:
                row = models.FederacionPago(
                    id_equipo=equipo.id_equipo,
                    id_temporada=temporada.id_temporada,
                    id_jugador=jid,
                )
                db.add(row)
            row.pagado = pagado
            row.pagado_en = datetime.utcnow() if pagado else None

    db.commit()
    return _build_out(db, equipo, temporada)


@router.get("/federacion/estado")
def federacion_estados(
    id_temporada: str | None = Query(default=None),
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area_read("cuotas")),
):
    """Mapa id_jugador → federacion_pagada. Solo quien puede ver cuotas."""
    temporada = _resolve_temporada(db, equipo, id_temporada)
    rows = (
        db.query(models.FederacionPago)
        .filter(
            models.FederacionPago.id_equipo == equipo.id_equipo,
            models.FederacionPago.id_temporada == temporada.id_temporada,
            models.FederacionPago.pagado.is_(True),
        )
        .all()
    )
    pagadas = {str(r.id_jugador) for r in rows}
    jugadoras = _jugadoras_activas(db, equipo.id_equipo)
    return {
        "id_temporada": str(temporada.id_temporada),
        "estados": {
            str(j.id_jugador): (str(j.id_jugador) in pagadas) for j, _ in jugadoras
        },
    }
