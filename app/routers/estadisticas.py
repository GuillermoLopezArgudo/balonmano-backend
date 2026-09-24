from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo, partido_del_equipo, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/estadisticas", tags=["estadisticas"])


def _assert_partido(db: Session, id_partido, id_equipo) -> models.Partido:
    partido = partido_del_equipo(db, id_partido, id_equipo)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


def _assert_jugador_club(db: Session, id_jugador, id_equipo) -> None:
    vinculo = (
        db.query(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_jugador == id_jugador,
            models.JugadorEquipo.id_equipo == id_equipo,
        )
        .first()
    )
    if not vinculo:
        raise HTTPException(status_code=403, detail="Jugador no pertenece a tu equipo")


def _partidos_ids(db: Session, id_equipo):
    rows = (
        db.query(models.Partido.id_partido)
        .filter(
            or_(
                models.Partido.id_equipo == id_equipo,
                models.Partido.id_equipo_local == id_equipo,
                models.Partido.id_equipo_visitante == id_equipo,
            )
        )
        .all()
    )
    return [r[0] for r in rows]


def _zona_bucket(zona: str | None) -> str | None:
    if not zona:
        return None
    z = zona.lower()
    if z in ("6m_izq", "6m_cen", "6m_der", "pivote", "6m"):
        return "6m"
    if z in ("9m_izq", "9m_cen", "9m_der", "frontal", "interior", "9m"):
        return "9m"
    if z in ("7m",):
        return "7m"
    if z in ("ext_izq", "ext_der", "extremo"):
        return "extremo"
    if z in ("contra", "contraataque"):
        return "contraataque"
    return None


def rebuild_estadistica_portero(
    db: Session,
    *,
    id_partido=None,
    id_jugador=None,
) -> int:
    """Recalcula estadistica_portero desde Parada + Gol recibido (fuente de verdad)."""
    tipos = (
        db.query(models.TipoAccion)
        .filter(models.TipoAccion.nombre.in_(("Parada", "Gol recibido")))
        .all()
    )
    if not tipos:
        return 0
    tipo_ids = [t.id_tipo_accion for t in tipos]
    tipo_por_id = {t.id_tipo_accion: t.nombre for t in tipos}

    q = db.query(models.Accion).filter(models.Accion.id_tipo_accion.in_(tipo_ids))
    if id_partido is not None:
        q = q.filter(models.Accion.id_partido == id_partido)
    if id_jugador is not None:
        q = q.filter(models.Accion.id_jugador == id_jugador)
    acciones = q.all()

    pairs = {(a.id_partido, a.id_jugador) for a in acciones}
    if id_partido is not None and id_jugador is not None:
        pairs.add((id_partido, id_jugador))

    updated = 0
    for pid, jid in pairs:
        acts = [
            a
            for a in acciones
            if a.id_partido == pid and a.id_jugador == jid
        ]
        if id_partido is not None and id_jugador is not None and (pid, jid) == (id_partido, id_jugador):
            acts = (
                db.query(models.Accion)
                .filter(
                    models.Accion.id_tipo_accion.in_(tipo_ids),
                    models.Accion.id_partido == pid,
                    models.Accion.id_jugador == jid,
                )
                .all()
            )

        fila = (
            db.query(models.EstadisticaPortero)
            .filter(
                models.EstadisticaPortero.id_partido == pid,
                models.EstadisticaPortero.id_jugador == jid,
            )
            .first()
        )
        if not acts:
            if fila:
                db.delete(fila)
            continue

        if not fila:
            fila = models.EstadisticaPortero(id_partido=pid, id_jugador=jid)
            db.add(fila)

        fila.paradas = 0
        fila.lanzamientos_recibidos = 0
        fila.goles_recibidos = 0
        fila.lanzamientos_6m = fila.paradas_6m = fila.goles_6m = 0
        fila.lanzamientos_9m = fila.paradas_9m = fila.goles_9m = 0
        fila.lanzamientos_7m = fila.paradas_7m = fila.goles_7m = 0
        fila.lanzamientos_extremo = fila.paradas_extremo = fila.goles_extremo = 0
        fila.lanzamientos_contraataque = fila.paradas_contraataque = fila.goles_contraataque = 0

        for a in acts:
            nombre = (tipo_por_id.get(a.id_tipo_accion) or "").lower()
            es_parada = "parada" in nombre
            es_gol_rec = "recibid" in nombre
            if not (es_parada or es_gol_rec):
                continue

            fila.lanzamientos_recibidos += 1
            if es_parada:
                fila.paradas += 1
            if es_gol_rec:
                fila.goles_recibidos += 1

            bucket = _zona_bucket(a.zona)
            if bucket == "6m":
                fila.lanzamientos_6m += 1
                if es_parada:
                    fila.paradas_6m += 1
                if es_gol_rec:
                    fila.goles_6m += 1
            elif bucket == "9m":
                fila.lanzamientos_9m += 1
                if es_parada:
                    fila.paradas_9m += 1
                if es_gol_rec:
                    fila.goles_9m += 1
            elif bucket == "7m":
                fila.lanzamientos_7m += 1
                if es_parada:
                    fila.paradas_7m += 1
                if es_gol_rec:
                    fila.goles_7m += 1
            elif bucket == "extremo":
                fila.lanzamientos_extremo += 1
                if es_parada:
                    fila.paradas_extremo += 1
                if es_gol_rec:
                    fila.goles_extremo += 1

            # Contraataque es un contexto (checkbox), no sustituye la zona de pista
            if getattr(a, "es_contraataque", False):
                fila.lanzamientos_contraataque += 1
                if es_parada:
                    fila.paradas_contraataque += 1
                if es_gol_rec:
                    fila.goles_contraataque += 1
        updated += 1

    return updated


@router.get("/jugadores/", response_model=list[schemas.EstadisticaJugadorOut])
def listar_jugador(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaJugador)
        .filter(models.EstadisticaJugador.id_partido.in_(ids))
        .order_by(models.EstadisticaJugador.id_estadistica.desc())
        .all()
    )


@router.post(
    "/jugadores/",
    response_model=schemas.EstadisticaJugadorOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_jugador(
    payload: schemas.EstadisticaJugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    existe = (
        db.query(models.EstadisticaJugador)
        .filter(
            models.EstadisticaJugador.id_partido == payload.id_partido,
            models.EstadisticaJugador.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if existe:
        for key, value in payload.model_dump().items():
            if key in ("id_partido", "id_jugador"):
                continue
            setattr(existe, key, value)
        db.commit()
        db.refresh(existe)
        return existe
    fila = models.EstadisticaJugador(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/jugadores/", response_model=schemas.EstadisticaJugadorOut)
def upsert_jugador(
    payload: schemas.EstadisticaJugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    return crear_jugador(payload, db, equipo)


@router.get("/lanzamientos/", response_model=list[schemas.EstadisticaLanzamientoOut])
def listar_lanzamiento(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaLanzamiento)
        .filter(models.EstadisticaLanzamiento.id_partido.in_(ids))
        .order_by(models.EstadisticaLanzamiento.id_estadistica.desc())
        .all()
    )


@router.post(
    "/lanzamientos/",
    response_model=schemas.EstadisticaLanzamientoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_lanzamiento(
    payload: schemas.EstadisticaLanzamientoCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    fila = models.EstadisticaLanzamiento(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.get("/porteros/", response_model=list[schemas.EstadisticaPorteroOut])
def listar_portero(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    return (
        db.query(models.EstadisticaPortero)
        .filter(models.EstadisticaPortero.id_partido.in_(ids))
        .order_by(models.EstadisticaPortero.id_estadistica.desc())
        .all()
    )


@router.post(
    "/porteros/",
    response_model=schemas.EstadisticaPorteroOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_portero(
    payload: schemas.EstadisticaPorteroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    existe = (
        db.query(models.EstadisticaPortero)
        .filter(
            models.EstadisticaPortero.id_partido == payload.id_partido,
            models.EstadisticaPortero.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if existe:
        for key, value in payload.model_dump().items():
            if key in ("id_partido", "id_jugador"):
                continue
            setattr(existe, key, value)
        db.commit()
        db.refresh(existe)
        return existe
    fila = models.EstadisticaPortero(**payload.model_dump())
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/porteros/", response_model=schemas.EstadisticaPorteroOut)
def upsert_portero(
    payload: schemas.EstadisticaPorteroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    return crear_portero(payload, db, equipo)


def _accion_out(fila: models.Accion) -> schemas.AccionOut:
    rj = fila.rival_jugador
    return schemas.AccionOut(
        id_accion=fila.id_accion,
        id_partido=fila.id_partido,
        id_jugador=fila.id_jugador,
        id_tipo_accion=fila.id_tipo_accion,
        minuto=fila.minuto,
        segundo=fila.segundo or 0,
        zona=fila.zona,
        zona_porteria=fila.zona_porteria,
        id_rival_jugador=fila.id_rival_jugador,
        rival_dorsal=rj.dorsal if rj else None,
        rival_nombre=rj.nombre if rj else None,
    )


@router.get("/acciones/", response_model=list[schemas.AccionOut])
def listar_acciones(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    ids = _partidos_ids(db, equipo.id_equipo)
    if not ids:
        return []
    filas = (
        db.query(models.Accion)
        .options(joinedload(models.Accion.rival_jugador))
        .filter(models.Accion.id_partido.in_(ids))
        .order_by(models.Accion.minuto, models.Accion.segundo)
        .all()
    )
    return [_accion_out(f) for f in filas]


@router.post("/acciones/", response_model=schemas.AccionOut, status_code=status.HTTP_201_CREATED)
def crear_accion(
    payload: schemas.AccionCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    try:
        fila = _crear_accion_impl(payload, db, equipo)
        db.refresh(fila)
        if fila.id_rival_jugador:
            fila = (
                db.query(models.Accion)
                .options(joinedload(models.Accion.rival_jugador))
                .filter(models.Accion.id_accion == fila.id_accion)
                .one()
            )
        return _accion_out(fila)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar la acción: {type(exc).__name__}: {exc}",
        ) from exc


def _crear_accion_impl(
    payload: schemas.AccionCreate,
    db: Session,
    equipo: models.Equipo,
):
    partido = _assert_partido(db, payload.id_partido, equipo.id_equipo)
    _assert_jugador_club(db, payload.id_jugador, equipo.id_equipo)
    tipo = db.get(models.TipoAccion, payload.id_tipo_accion)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de acción no encontrado")

    if payload.id_rival_jugador:
        rj = db.get(models.RivalJugador, payload.id_rival_jugador)
        if not rj or not rj.activo:
            raise HTTPException(status_code=404, detail="Jugadora rival no encontrada")
        if partido.id_rival and rj.id_rival != partido.id_rival:
            raise HTTPException(
                status_code=400,
                detail="La jugadora rival no pertenece al rival de este partido",
            )

    fila = models.Accion(**payload.model_dump())
    db.add(fila)

    stats = (
        db.query(models.EstadisticaJugador)
        .filter(
            models.EstadisticaJugador.id_partido == payload.id_partido,
            models.EstadisticaJugador.id_jugador == payload.id_jugador,
        )
        .first()
    )
    if not stats:
        stats = models.EstadisticaJugador(
            id_partido=payload.id_partido,
            id_jugador=payload.id_jugador,
        )
        db.add(stats)
        db.flush()

    nombre = tipo.nombre.lower()
    es_gol = "gol" in nombre and "recibid" not in nombre
    es_tiro = es_gol or (
        "lanzamiento" in nombre or "fallado" in nombre or "fuera" in nombre or "poste" in nombre
    )

    if es_gol:
        stats.goles += 1
        stats.lanzamientos += 1
    elif es_tiro:
        stats.lanzamientos += 1
        stats.lanzamientos_fallados += 1
    elif "asistencia" in nombre:
        stats.asistencias += 1
    elif "pérdida" in nombre or "perdida" in nombre:
        stats.perdidas += 1
    elif "recuperación" in nombre or "recuperacion" in nombre:
        stats.recuperaciones += 1
    elif "exclusión" in nombre or "exclusion" in nombre:
        stats.exclusiones_2min += 1
    elif "amarilla" in nombre:
        stats.amarillas += 1
    elif "roja" in nombre:
        stats.rojas += 1
    elif "azul" in nombre:
        stats.azules += 1

    # Desglose por zona → tabla estadistica_lanzamiento (no estadistica_jugador)
    if es_tiro and payload.zona:
        zona_stats = (
            db.query(models.EstadisticaLanzamiento)
            .filter(
                models.EstadisticaLanzamiento.id_partido == payload.id_partido,
                models.EstadisticaLanzamiento.id_jugador == payload.id_jugador,
            )
            .first()
        )
        if not zona_stats:
            zona_stats = models.EstadisticaLanzamiento(
                id_partido=payload.id_partido,
                id_jugador=payload.id_jugador,
            )
            db.add(zona_stats)
            db.flush()

        z = payload.zona.lower()
        if z in ("6m_izq", "6m_cen", "6m_der", "pivote", "6m"):
            zona_stats.lanzamientos_6m += 1
            if es_gol:
                zona_stats.goles_6m += 1
        elif z in ("9m_izq", "9m_cen", "9m_der", "frontal", "interior", "9m"):
            zona_stats.lanzamientos_9m += 1
            if es_gol:
                zona_stats.goles_9m += 1
        elif z in ("7m",):
            zona_stats.lanzamientos_7m += 1
            if es_gol:
                zona_stats.goles_7m += 1
        elif z in ("ext_izq", "ext_der", "extremo"):
            zona_stats.lanzamientos_extremo += 1
            if es_gol:
                zona_stats.goles_extremo += 1

        if payload.es_contraataque:
            zona_stats.lanzamientos_contraataque += 1
            if es_gol:
                zona_stats.goles_contraataque += 1

    # Parada / gol recibido: recalcular totales de portera desde acciones
    if "parada" in nombre or ("gol" in nombre and "recibid" in nombre):
        rebuild_estadistica_portero(
            db,
            id_partido=payload.id_partido,
            id_jugador=payload.id_jugador,
        )

    db.commit()
    db.refresh(fila)
    return fila


@router.get("/resumen/jugadores", response_model=list[schemas.ResumenJugador])
def resumen_jugadores(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    jugador_ids = [
        r[0]
        for r in db.query(models.JugadorEquipo.id_jugador)
        .filter(models.JugadorEquipo.id_equipo == equipo.id_equipo)
        .all()
    ]
    if not jugador_ids:
        return []
    filas = (
        db.query(
            models.Jugador.id_jugador,
            models.Jugador.nombre,
            models.Jugador.apellido,
            func.count(models.EstadisticaJugador.id_estadistica).label("partidos"),
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0).label("goles"),
            func.coalesce(func.sum(models.EstadisticaJugador.asistencias), 0).label("asistencias"),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0).label("lanzamientos"),
            func.coalesce(func.sum(models.EstadisticaJugador.perdidas), 0).label("perdidas"),
            func.coalesce(func.sum(models.EstadisticaJugador.amarillas), 0).label("amarillas"),
            func.coalesce(func.sum(models.EstadisticaJugador.exclusiones_2min), 0).label(
                "exclusiones_2min"
            ),
            func.coalesce(func.sum(models.EstadisticaJugador.rojas), 0).label("rojas"),
            func.coalesce(func.sum(models.EstadisticaJugador.azules), 0).label("azules"),
            func.coalesce(func.sum(models.EstadisticaJugador.minutos_jugados), 0).label(
                "minutos_jugados"
            ),
        )
        .outerjoin(
            models.EstadisticaJugador,
            models.EstadisticaJugador.id_jugador == models.Jugador.id_jugador,
        )
        .filter(models.Jugador.id_jugador.in_(jugador_ids))
        .group_by(models.Jugador.id_jugador, models.Jugador.nombre, models.Jugador.apellido)
        .order_by(func.coalesce(func.sum(models.EstadisticaJugador.goles), 0).desc())
        .all()
    )
    out = []
    for fila in filas:
        row = dict(fila._mapping)
        lanz = int(row.get("lanzamientos") or 0)
        perd = int(row.get("perdidas") or 0)
        denom = lanz + perd
        row["pct_perdidas"] = round((perd / denom) * 100, 1) if denom else 0.0
        out.append(schemas.ResumenJugador.model_validate(row))
    return out


@router.delete("/jugadores/{id_estadistica}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_jugador(
    id_estadistica: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("directo")),
):
    fila = db.get(models.EstadisticaJugador, id_estadistica)
    if not fila:
        raise HTTPException(status_code=404, detail="Estadística no encontrada")
    _assert_partido(db, fila.id_partido, equipo.id_equipo)
    db.delete(fila)
    db.commit()
