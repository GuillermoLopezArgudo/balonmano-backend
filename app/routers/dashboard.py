from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo
from app.database import get_db
from app.routers.jugadores import _jugador_out, _vinculo_equipo
from app.routers.partidos import _partido_out

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Zonas de origen que se marcan en Directo (pista) + contraataque (checkbox)
ZONAS_PISTA_ORDEN = (
    "ext_izq",
    "6m_izq",
    "6m_cen",
    "6m_der",
    "ext_der",
    "7m",
    "9m_izq",
    "9m_cen",
    "9m_der",
    "contraataque",
)


def _zona_canonica(zona: str | None) -> str | None:
    if not zona:
        return None
    z = zona.lower().strip()
    aliases = {
        "6m": "6m_cen",
        "pivote": "6m_cen",
        "9m": "9m_cen",
        "frontal": "9m_cen",
        "interior": "9m_cen",
        "extremo": "ext_izq",
    }
    z = aliases.get(z, z)
    return z if z in ZONAS_PISTA_ORDEN else None


def _zonas_vacias_tiro() -> dict:
    return {k: {"lanzamientos": 0, "goles": 0} for k in ZONAS_PISTA_ORDEN}


def _zonas_vacias_parada() -> dict:
    return {k: {"paradas": 0, "lanzamientos": 0} for k in ZONAS_PISTA_ORDEN}


@router.get("/", response_model=schemas.DashboardOut)
def resumen(
    equipo: models.Equipo = Depends(get_current_equipo),
    db: Session = Depends(get_db),
):
    id_eq = equipo.id_equipo
    partidos = (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.equipo_local).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_visitante).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_owner).joinedload(models.Equipo.datos),
            joinedload(models.Partido.rival),
            joinedload(models.Partido.temporada),
        )
        .filter(
            or_(
                models.Partido.id_equipo == id_eq,
                models.Partido.id_equipo_local == id_eq,
                models.Partido.id_equipo_visitante == id_eq,
            )
        )
        .order_by(models.Partido.fecha.desc())
        .all()
    )

    goles_totales = 0
    for p in partidos:
        if (p.estado or "") != "jugado":
            continue
        if p.id_rival and p.id_equipo == id_eq:
            goles_totales += (p.goles_local if p.es_local else p.goles_visitante) or 0
        elif p.id_equipo_local == id_eq:
            goles_totales += p.goles_local or 0
        else:
            goles_totales += p.goles_visitante or 0

    stats = (
        db.query(
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.perdidas), 0),
        )
        .join(models.JugadorEquipo, models.JugadorEquipo.id_jugador == models.EstadisticaJugador.id_jugador)
        .filter(models.JugadorEquipo.id_equipo == id_eq)
        .one()
    )
    goles_stats, lanzamientos, perdidas = (int(stats[0]), int(stats[1]), int(stats[2]))
    if goles_stats:
        goles_totales = goles_stats
    efectividad = round((goles_totales / lanzamientos) * 100, 1) if lanzamientos else 0.0

    pos_rows = (
        db.query(
            models.Posicion.nombre,
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0),
        )
        .select_from(models.Posicion)
        .outerjoin(models.JugadorPosicion, models.JugadorPosicion.id_posicion == models.Posicion.id_posicion)
        .outerjoin(models.JugadorEquipo, models.JugadorEquipo.id_jugador == models.JugadorPosicion.id_jugador)
        .outerjoin(
            models.EstadisticaJugador,
            models.EstadisticaJugador.id_jugador == models.JugadorPosicion.id_jugador,
        )
        .filter(or_(models.JugadorEquipo.id_equipo == id_eq, models.JugadorEquipo.id_equipo.is_(None)))
        .group_by(models.Posicion.nombre)
        .all()
    )
    # Simplificar: agrupar por familia de posición
    familias = {"Extremo": 0, "Lateral": 0, "Central": 0, "Pivote": 0, "Portero": 0}
    familia_lanz = {k: 0 for k in familias}
    for nombre, goles, lanz in pos_rows:
        key = next((k for k in familias if k.lower() in nombre.lower()), None)
        if key:
            familias[key] += int(goles)
            familia_lanz[key] += int(lanz)

    efectividad_por_posicion = [
        {
            "posicion": k,
            "efectividad": round((familias[k] / familia_lanz[k]) * 100, 1) if familia_lanz[k] else 0,
        }
        for k in ["Extremo", "Lateral", "Central", "Pivote"]
    ]

    from datetime import datetime, timezone

    ahora = datetime.now(timezone.utc)
    # Solo cuentan partidos cerrados a mano como jugados (no por fecha).
    jugados = [p for p in partidos if (p.estado or "") == "jugado"]
    proximos = [
        p
        for p in partidos
        if (p.estado or "programado") == "programado" and p.fecha > ahora
    ]
    proximos.sort(key=lambda x: x.fecha)

    gk_stats = (
        db.query(
            func.coalesce(func.sum(models.EstadisticaPortero.paradas), 0),
            func.coalesce(func.sum(models.EstadisticaPortero.lanzamientos_recibidos), 0),
            func.coalesce(func.sum(models.EstadisticaPortero.goles_recibidos), 0),
        )
        .join(
            models.JugadorEquipo,
            models.JugadorEquipo.id_jugador == models.EstadisticaPortero.id_jugador,
        )
        .filter(models.JugadorEquipo.id_equipo == id_eq)
        .one()
    )
    paradas = int(gk_stats[0] or 0)
    recibidos = int(gk_stats[1] or 0)
    goles_recibidos = int(gk_stats[2] or 0)
    if not recibidos and (paradas or goles_recibidos):
        recibidos = paradas + goles_recibidos
    efectividad_paradas = round((paradas / recibidos) * 100, 1) if recibidos else 0.0

    return schemas.DashboardOut(
        equipo_nombre=equipo.datos.nombre if equipo.datos else equipo.correo,
        partidos_jugados=len(jugados),
        goles_totales=goles_totales,
        efectividad=efectividad,
        perdidas=perdidas,
        efectividad_por_posicion=efectividad_por_posicion,
        ultimos_partidos=[_partido_out(p) for p in jugados[:5]],
        proximos_partidos=[_partido_out(p) for p in proximos[:5]],
        paradas=paradas,
        lanzamientos_recibidos=recibidos,
        goles_recibidos=goles_recibidos,
        efectividad_paradas=efectividad_paradas,
    )


@router.get("/jugador/{id_jugador}", response_model=schemas.JugadorDetalleOut)
def jugador_detalle(
    id_jugador: str,
    equipo: models.Equipo = Depends(get_current_equipo),
    db: Session = Depends(get_db),
):
    jugador = (
        db.query(models.Jugador)
        .options(
            joinedload(models.Jugador.equipos).joinedload(models.JugadorEquipo.equipo).joinedload(
                models.Equipo.datos
            ),
            joinedload(models.Jugador.posiciones).joinedload(models.JugadorPosicion.posicion),
        )
        .filter(models.Jugador.id_jugador == id_jugador)
        .first()
    )
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if not _vinculo_equipo(db, id_jugador, equipo.id_equipo):
        raise HTTPException(status_code=403, detail="No pertenece a tu equipo")

    posiciones = [jp.posicion.nombre for jp in jugador.posiciones if jp.posicion]
    es_portero = any("portero" in (p or "").lower() for p in posiciones)

    totales = (
        db.query(
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.asistencias), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.minutos_jugados), 0),
            func.count(models.EstadisticaJugador.id_estadistica),
            func.coalesce(func.sum(models.EstadisticaJugador.perdidas), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.recuperaciones), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.faltas_cometidas), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.faltas_recibidas), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.amarillas), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.exclusiones_2min), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.rojas), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.azules), 0),
        )
        .filter(models.EstadisticaJugador.id_jugador == id_jugador)
        .one()
    )
    (
        goles,
        lanzamientos,
        asistencias,
        minutos,
        partidos_campo,
        perdidas,
        recuperaciones,
        faltas_cometidas,
        faltas_recibidas,
        amarillas,
        exclusiones_2min,
        rojas,
        azules,
    ) = (int(x) for x in totales)
    efectividad = round((goles / lanzamientos) * 100, 1) if lanzamientos else 0.0
    denom_perd = lanzamientos + perdidas
    pct_perdidas = round((perdidas / denom_perd) * 100, 1) if denom_perd else 0.0

    por_partido = (
        db.query(
            models.Partido.fecha,
            models.EstadisticaJugador.goles,
            models.EstadisticaJugador.lanzamientos,
        )
        .join(models.Partido, models.Partido.id_partido == models.EstadisticaJugador.id_partido)
        .filter(models.EstadisticaJugador.id_jugador == id_jugador)
        .order_by(models.Partido.fecha.desc())
        .limit(8)
        .all()
    )

    zonas_row = (
        db.query(models.EstadisticaLanzamiento)
        .filter(models.EstadisticaLanzamiento.id_jugador == id_jugador)
        .all()
    )
    # Preferir desglose fino desde acciones (6I/6C/6D…); fallback a agregados legacy
    zonas = _zonas_vacias_tiro()
    acciones_tiro = (
        db.query(models.Accion, models.TipoAccion.nombre)
        .join(models.TipoAccion, models.TipoAccion.id_tipo_accion == models.Accion.id_tipo_accion)
        .filter(
            models.Accion.id_jugador == id_jugador,
            models.Accion.zona.isnot(None),
        )
        .all()
    )
    hubo_acciones_zona = False
    for accion, tipo_nombre in acciones_tiro:
        nombre = (tipo_nombre or "").lower()
        es_gol = "gol" in nombre and "recibid" not in nombre
        es_fallado = (
            "lanzamiento" in nombre
            or "fallado" in nombre
            or "fuera" in nombre
            or "poste" in nombre
        )
        if not es_gol and not es_fallado:
            continue
        key = _zona_canonica(accion.zona)
        if key:
            hubo_acciones_zona = True
            zonas[key]["lanzamientos"] += 1
            if es_gol:
                zonas[key]["goles"] += 1
        if getattr(accion, "es_contraataque", False):
            hubo_acciones_zona = True
            zonas["contraataque"]["lanzamientos"] += 1
            if es_gol:
                zonas["contraataque"]["goles"] += 1

    if not hubo_acciones_zona:
        # Datos antiguos solo en estadistica_lanzamiento (sin lado)
        for z in zonas_row:
            zonas["6m_cen"]["lanzamientos"] += z.lanzamientos_6m
            zonas["6m_cen"]["goles"] += z.goles_6m
            zonas["9m_cen"]["lanzamientos"] += z.lanzamientos_9m
            zonas["9m_cen"]["goles"] += z.goles_9m
            zonas["7m"]["lanzamientos"] += z.lanzamientos_7m
            zonas["7m"]["goles"] += z.goles_7m
            zonas["ext_izq"]["lanzamientos"] += z.lanzamientos_extremo
            zonas["ext_izq"]["goles"] += z.goles_extremo
            zonas["contraataque"]["lanzamientos"] += z.lanzamientos_contraataque
            zonas["contraataque"]["goles"] += z.goles_contraataque

    porteros = (
        db.query(models.EstadisticaPortero)
        .filter(models.EstadisticaPortero.id_jugador == id_jugador)
        .all()
    )
    paradas = sum(p.paradas for p in porteros)
    recibidos = sum(p.lanzamientos_recibidos for p in porteros)
    goles_recibidos = sum(p.goles_recibidos for p in porteros)
    efectividad_paradas = round((paradas / recibidos) * 100, 1) if recibidos else 0.0
    mapa_paradas = _zonas_vacias_parada()
    acciones_gk = (
        db.query(models.Accion, models.TipoAccion.nombre)
        .join(models.TipoAccion, models.TipoAccion.id_tipo_accion == models.Accion.id_tipo_accion)
        .filter(
            models.Accion.id_jugador == id_jugador,
            models.Accion.zona.isnot(None),
        )
        .all()
    )
    hubo_gk_zona = False
    for accion, tipo_nombre in acciones_gk:
        nombre = (tipo_nombre or "").lower()
        es_parada = "parada" in nombre
        es_gol_recibido = "gol" in nombre and "recibid" in nombre
        if not es_parada and not es_gol_recibido:
            continue
        key = _zona_canonica(accion.zona)
        if key:
            hubo_gk_zona = True
            mapa_paradas[key]["lanzamientos"] += 1
            if es_parada:
                mapa_paradas[key]["paradas"] += 1
        if getattr(accion, "es_contraataque", False):
            hubo_gk_zona = True
            mapa_paradas["contraataque"]["lanzamientos"] += 1
            if es_parada:
                mapa_paradas["contraataque"]["paradas"] += 1

    if not hubo_gk_zona:
        for p in porteros:
            mapa_paradas["6m_cen"]["paradas"] += p.paradas_6m
            mapa_paradas["6m_cen"]["lanzamientos"] += p.lanzamientos_6m
            mapa_paradas["9m_cen"]["paradas"] += p.paradas_9m
            mapa_paradas["9m_cen"]["lanzamientos"] += p.lanzamientos_9m
            mapa_paradas["7m"]["paradas"] += p.paradas_7m
            mapa_paradas["7m"]["lanzamientos"] += p.lanzamientos_7m
            mapa_paradas["ext_izq"]["paradas"] += p.paradas_extremo
            mapa_paradas["ext_izq"]["lanzamientos"] += p.lanzamientos_extremo
            mapa_paradas["contraataque"]["paradas"] += p.paradas_contraataque
            mapa_paradas["contraataque"]["lanzamientos"] += p.lanzamientos_contraataque

    partidos_gk = len(porteros)
    partidos = max(partidos_campo, partidos_gk)

    if es_portero and porteros:
        por_gk = (
            db.query(
                models.Partido.fecha,
                models.EstadisticaPortero.paradas,
                models.EstadisticaPortero.lanzamientos_recibidos,
            )
            .join(models.Partido, models.Partido.id_partido == models.EstadisticaPortero.id_partido)
            .filter(models.EstadisticaPortero.id_jugador == id_jugador)
            .order_by(models.Partido.fecha.desc())
            .limit(8)
            .all()
        )
        ultimos = []
        for f, par, rec in reversed(por_gk):
            pct = round((par / rec) * 100, 1) if rec else 0
            ultimos.append(
                {
                    "fecha": str(f.date()) if hasattr(f, "date") else str(f),
                    "valor": pct,
                    "detalle": f"{par}/{rec}",
                }
            )
    else:
        ultimos = []
        for f, g, lanz in reversed(por_partido):
            pct = round((g / lanz) * 100, 1) if lanz else 0
            ultimos.append(
                {
                    "fecha": str(f.date()) if hasattr(f, "date") else str(f),
                    "valor": pct,
                    "detalle": f"{g}/{lanz}",
                }
            )

    asis_rows = (
        db.query(models.SesionAsistencia.estado, func.count())
        .join(
            models.SesionEntrenamiento,
            models.SesionEntrenamiento.id_sesion == models.SesionAsistencia.id_sesion,
        )
        .filter(
            models.SesionAsistencia.id_jugador == id_jugador,
            models.SesionEntrenamiento.id_equipo == equipo.id_equipo,
        )
        .group_by(models.SesionAsistencia.estado)
        .all()
    )
    asis_map = {estado: int(n) for estado, n in asis_rows}
    asis_presentes = asis_map.get("presente", 0)
    asis_faltas = asis_map.get("falta", 0)
    asis_just = asis_map.get("justificada", 0)
    asis_sesiones = asis_presentes + asis_faltas + asis_just
    # % = presentes / (presentes + faltas); justificada no penaliza
    asis_denom = asis_presentes + asis_faltas
    asis_pct = round((asis_presentes / asis_denom) * 100, 1) if asis_denom else 0.0

    return schemas.JugadorDetalleOut(
        jugador=_jugador_out(jugador),
        goles=goles,
        lanzamientos=lanzamientos,
        efectividad=efectividad,
        asistencias=asistencias,
        minutos_jugados=minutos,
        partidos=partidos,
        perdidas=perdidas,
        recuperaciones=recuperaciones,
        faltas_cometidas=faltas_cometidas,
        faltas_recibidas=faltas_recibidas,
        pct_perdidas=pct_perdidas,
        amarillas=amarillas,
        exclusiones_2min=exclusiones_2min,
        rojas=rojas,
        azules=azules,
        es_portero=es_portero,
        paradas=paradas,
        lanzamientos_recibidos=recibidos,
        goles_recibidos=goles_recibidos,
        efectividad_paradas=efectividad_paradas,
        asistencia_entrenamientos=schemas.JugadorAsistenciaResumen(
            sesiones=asis_sesiones,
            presentes=asis_presentes,
            faltas=asis_faltas,
            justificadas=asis_just,
            pct_asistencia=asis_pct,
        ),
        goles_por_partido=[
            {"fecha": str(f.date()) if hasattr(f, "date") else str(f), "goles": int(g)}
            for f, g, _ in por_partido
        ],
        zonas=zonas,
        mapa_paradas=mapa_paradas,
        ultimos_partidos=ultimos,
    )
