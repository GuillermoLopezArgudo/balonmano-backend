from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_equipo
from app.database import get_db
from app.routers.jugadores import _jugador_out
from app.routers.partidos import _partido_out

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
    jugados = [p for p in partidos if p.fecha <= ahora]
    proximos = [p for p in partidos if p.fecha > ahora]
    proximos.sort(key=lambda x: x.fecha)

    return schemas.DashboardOut(
        equipo_nombre=equipo.datos.nombre if equipo.datos else equipo.correo,
        partidos_jugados=len(jugados),
        goles_totales=goles_totales,
        efectividad=efectividad,
        perdidas=perdidas,
        efectividad_por_posicion=efectividad_por_posicion,
        ultimos_partidos=[_partido_out(p) for p in jugados[:5]],
        proximos_partidos=[_partido_out(p) for p in proximos[:5]],
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
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    posiciones = [jp.posicion.nombre for jp in jugador.posiciones if jp.posicion]
    es_portero = any("portero" in (p or "").lower() for p in posiciones)

    totales = (
        db.query(
            func.coalesce(func.sum(models.EstadisticaJugador.goles), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.lanzamientos), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.asistencias), 0),
            func.coalesce(func.sum(models.EstadisticaJugador.minutos_jugados), 0),
            func.count(models.EstadisticaJugador.id_estadistica),
        )
        .filter(models.EstadisticaJugador.id_jugador == id_jugador)
        .one()
    )
    goles, lanzamientos, asistencias, minutos, partidos_campo = (int(x) for x in totales)
    efectividad = round((goles / lanzamientos) * 100, 1) if lanzamientos else 0.0

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
    zonas = {
        "6m": {"lanzamientos": 0, "goles": 0},
        "9m": {"lanzamientos": 0, "goles": 0},
        "7m": {"lanzamientos": 0, "goles": 0},
        "extremo": {"lanzamientos": 0, "goles": 0},
        "contraataque": {"lanzamientos": 0, "goles": 0},
    }
    for z in zonas_row:
        zonas["6m"]["lanzamientos"] += z.lanzamientos_6m
        zonas["6m"]["goles"] += z.goles_6m
        zonas["9m"]["lanzamientos"] += z.lanzamientos_9m
        zonas["9m"]["goles"] += z.goles_9m
        zonas["7m"]["lanzamientos"] += z.lanzamientos_7m
        zonas["7m"]["goles"] += z.goles_7m
        zonas["extremo"]["lanzamientos"] += z.lanzamientos_extremo
        zonas["extremo"]["goles"] += z.goles_extremo
        zonas["contraataque"]["lanzamientos"] += z.lanzamientos_contraataque
        zonas["contraataque"]["goles"] += z.goles_contraataque

    porteros = (
        db.query(models.EstadisticaPortero)
        .filter(models.EstadisticaPortero.id_jugador == id_jugador)
        .all()
    )
    paradas = sum(p.paradas for p in porteros)
    recibidos = sum(p.lanzamientos_recibidos for p in porteros)
    efectividad_paradas = round((paradas / recibidos) * 100, 1) if recibidos else 0.0
    mapa_paradas = {
        "6m": {"paradas": 0, "lanzamientos": 0},
        "9m": {"paradas": 0, "lanzamientos": 0},
        "7m": {"paradas": 0, "lanzamientos": 0},
        "extremo": {"paradas": 0, "lanzamientos": 0},
        "contraataque": {"paradas": 0, "lanzamientos": 0},
    }
    for p in porteros:
        mapa_paradas["6m"]["paradas"] += p.paradas_6m
        mapa_paradas["6m"]["lanzamientos"] += p.lanzamientos_6m
        mapa_paradas["9m"]["paradas"] += p.paradas_9m
        mapa_paradas["9m"]["lanzamientos"] += p.lanzamientos_9m
        mapa_paradas["7m"]["paradas"] += p.paradas_7m
        mapa_paradas["7m"]["lanzamientos"] += p.lanzamientos_7m
        mapa_paradas["extremo"]["paradas"] += p.paradas_extremo
        mapa_paradas["extremo"]["lanzamientos"] += p.lanzamientos_extremo
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

    return schemas.JugadorDetalleOut(
        jugador=_jugador_out(jugador),
        goles=goles,
        lanzamientos=lanzamientos,
        efectividad=efectividad,
        asistencias=asistencias,
        minutos_jugados=minutos,
        partidos=partidos,
        es_portero=es_portero,
        paradas=paradas,
        lanzamientos_recibidos=recibidos,
        efectividad_paradas=efectividad_paradas,
        goles_por_partido=[
            {"fecha": str(f.date()) if hasattr(f, "date") else str(f), "goles": int(g)}
            for f, g, _ in por_partido
        ],
        zonas=zonas,
        mapa_paradas=mapa_paradas,
        ultimos_partidos=ultimos,
    )
