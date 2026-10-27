"""Dashboard y detalle de jugador."""

from pydantic import BaseModel
from app.schemas.jugadores import JugadorOut
from app.schemas.partidos import PartidoOut


class DashboardOut(BaseModel):
    equipo_nombre: str
    partidos_jugados: int
    goles_totales: int
    efectividad: float
    perdidas: int
    efectividad_por_posicion: list[dict]
    ultimos_partidos: list[PartidoOut]
    proximos_partidos: list[PartidoOut]
    paradas: int = 0
    lanzamientos_recibidos: int = 0
    goles_recibidos: int = 0
    efectividad_paradas: float = 0.0


class JugadorAsistenciaResumen(BaseModel):
    sesiones: int = 0
    presentes: int = 0
    faltas: int = 0
    justificadas: int = 0
    pct_asistencia: float = 0.0


class JugadorDetalleOut(BaseModel):
    jugador: JugadorOut
    goles: int
    lanzamientos: int
    efectividad: float
    asistencias: int
    minutos_jugados: int
    partidos: int
    perdidas: int = 0
    recuperaciones: int = 0
    faltas_cometidas: int = 0
    faltas_recibidas: int = 0
    pct_perdidas: float = 0.0
    amarillas: int = 0
    exclusiones_2min: int = 0
    rojas: int = 0
    azules: int = 0
    es_portero: bool = False
    paradas: int = 0
    lanzamientos_recibidos: int = 0
    goles_recibidos: int = 0
    efectividad_paradas: float = 0.0
    goles_por_partido: list[dict]
    zonas: dict
    mapa_paradas: dict = {}
    ultimos_partidos: list[dict] = []
    asistencia_entrenamientos: JugadorAsistenciaResumen | None = None
