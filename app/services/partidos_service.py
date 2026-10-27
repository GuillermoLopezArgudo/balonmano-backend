"""Servicios de dominio para partidos.

Carga con relaciones, serialización a ``PartidoOut`` (resolviendo local/visitante
según partidos contra rivales o entre equipos), filtro de ámbito por equipo y
comprobación de editabilidad según el estado de la temporada. Reutilizado por
``app.routers.partidos`` y ``app.routers.dashboard``.
"""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas


def club_nombre(equipo: models.Equipo | None) -> str | None:
    if not equipo:
        return None
    return equipo.datos.nombre if equipo.datos else None


def partido_out(partido: models.Partido) -> schemas.PartidoOut:
    rival_nombre = partido.rival.nombre if partido.rival else None
    owner = partido.equipo_owner
    owner_nombre = club_nombre(owner)

    if partido.id_rival and partido.id_equipo:
        es_local = bool(partido.es_local) if partido.es_local is not None else True
        local_nombre = owner_nombre if es_local else rival_nombre
        visit_nombre = rival_nombre if es_local else owner_nombre
        # IDs sintetizados para que el FE compare con equipo.id_equipo
        id_local = partido.id_equipo if es_local else partido.id_rival
        id_visit = partido.id_rival if es_local else partido.id_equipo
    else:
        local_nombre = club_nombre(partido.equipo_local)
        visit_nombre = club_nombre(partido.equipo_visitante)
        id_local = partido.id_equipo_local
        id_visit = partido.id_equipo_visitante
        es_local = None

    return schemas.PartidoOut(
        id_partido=partido.id_partido,
        id_equipo_local=id_local,
        id_equipo_visitante=id_visit,
        id_equipo=partido.id_equipo,
        id_rival=partido.id_rival,
        es_local=es_local if es_local is not None else (
            bool(partido.es_local) if partido.es_local is not None else None
        ),
        id_temporada=partido.id_temporada,
        fecha=partido.fecha,
        jornada=partido.jornada,
        pabellon=partido.pabellon,
        competicion=partido.competicion,
        goles_local=partido.goles_local,
        goles_visitante=partido.goles_visitante,
        estado=getattr(partido, "estado", None) or "programado",
        equipo_local_nombre=local_nombre,
        equipo_visitante_nombre=visit_nombre,
        temporada_nombre=partido.temporada.nombre if partido.temporada else None,
        temporada_estado=partido.temporada.estado if partido.temporada else None,
    )


def load_partido(db: Session, id_partido: str) -> models.Partido | None:
    return (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.equipo_local).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_visitante).joinedload(models.Equipo.datos),
            joinedload(models.Partido.equipo_owner).joinedload(models.Equipo.datos),
            joinedload(models.Partido.rival),
            joinedload(models.Partido.temporada),
        )
        .filter(models.Partido.id_partido == id_partido)
        .first()
    )


def assert_editable(partido: models.Partido) -> None:
    temp = partido.temporada
    if not temp:
        return
    if temp.estado == "archivada":
        raise HTTPException(status_code=400, detail="Temporada archivada: no se puede editar")
    if temp.estado == "cerrada" and partido.estado not in ("programado", "aplazado"):
        raise HTTPException(
            status_code=400,
            detail="En temporada cerrada solo se pueden completar partidos aplazados/programados",
        )


def scope_filter(id_equipo):
    return or_(
        models.Partido.id_equipo == id_equipo,
        models.Partido.id_equipo_local == id_equipo,
        models.Partido.id_equipo_visitante == id_equipo,
    )
