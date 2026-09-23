import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.auth import hash_password as hash_password  # reexport

class DatosEquipoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    nombre_corto: str | None = Field(default=None, max_length=80)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    codigo_federativo: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    pabellon: str | None = Field(default=None, max_length=200)
    img_escudo: str | None = Field(default=None, max_length=255)


class DatosEquipoOut(DatosEquipoIn):
    model_config = ConfigDict(from_attributes=True)

    id_equipo: uuid.UUID


class DatosEquipoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    nombre_corto: str | None = Field(default=None, max_length=80)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    codigo_federativo: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    pabellon: str | None = Field(default=None, max_length=200)
    img_escudo: str | None = Field(default=None, max_length=255)


class EquipoCreate(BaseModel):
    correo: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    datos: DatosEquipoIn


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_equipo: uuid.UUID
    correo: str
    datos: DatosEquipoOut | None = None


class CuentaUpdate(BaseModel):
    correo: str | None = Field(default=None, min_length=3, max_length=255)
    # actual puede ser corta (cuentas legacy); la nueva exige 8+
    password_actual: str | None = Field(default=None, min_length=1, max_length=128)
    password_nueva: str | None = Field(default=None, min_length=8, max_length=128)
    nombre_display: str | None = Field(default=None, max_length=150)
    entrenador_nombre: str | None = Field(default=None, max_length=150)


class TemporadaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    fecha_inicio: date
    fecha_fin: date
    activar: bool = True


class TemporadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_temporada: uuid.UUID
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    estado: str = "activa"
    cerrada_en: datetime | None = None
    pendientes: int = 0


class TemporadaAbrir(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    fecha_inicio: date
    fecha_fin: date
    cerrar_anterior: bool = True


class EquipoTemporadaCreate(BaseModel):
    id_equipo: uuid.UUID
    id_temporada: uuid.UUID
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)


class EquipoTemporadaOut(EquipoTemporadaCreate):
    model_config = ConfigDict(from_attributes=True)


class PosicionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_posicion: int
    nombre: str


class TipoAccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_accion: int
    nombre: str


class JugadorCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    fecha_nacimiento: date | None = None
    altura_cm: int | None = Field(default=None, ge=100, le=250)
    peso_kg: int | None = Field(default=None, ge=30, le=200)
    img_foto: str | None = Field(default=None, max_length=255)
    id_equipo: uuid.UUID | None = None
    dorsal: int = Field(ge=0, le=99)
    id_posicion: int | None = None
    fecha_alta: date | None = None
    activo: bool = True


class JugadorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    apellido: str | None = Field(default=None, min_length=1, max_length=100)
    fecha_nacimiento: date | None = None
    altura_cm: int | None = Field(default=None, ge=100, le=250)
    peso_kg: int | None = Field(default=None, ge=30, le=200)
    img_foto: str | None = Field(default=None, max_length=255)
    dorsal: int | None = Field(default=None, ge=0, le=99)
    id_posicion: int | None = None
    activo: bool | None = None


class JugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    fecha_nacimiento: date | None = None
    altura_cm: int | None = None
    peso_kg: int | None = None
    img_foto: str | None = Field(default=None, max_length=255)
    dorsal: int | None = None
    id_equipo: uuid.UUID | None = None
    equipo_nombre: str | None = None
    posiciones: list[str] = []
    id_posicion: int | None = None
    activo: bool = True

class PartidoCreate(BaseModel):
    """Crea un partido del club autenticado contra un rival propio."""

    id_rival: uuid.UUID
    es_local: bool = True
    id_temporada: uuid.UUID
    fecha: datetime
    jornada: int | None = Field(default=None, ge=1)
    pabellon: str | None = Field(default=None, max_length=200)
    competicion: str | None = Field(default=None, max_length=100)
    goles_local: int = Field(default=0, ge=0)
    goles_visitante: int = Field(default=0, ge=0)
    estado: str = Field(default="programado", pattern="^(programado|aplazado|jugado|no_disputado)$")


class PartidoUpdate(BaseModel):
    goles_local: int | None = Field(default=None, ge=0)
    goles_visitante: int | None = Field(default=None, ge=0)
    jornada: int | None = Field(default=None, ge=1)
    fecha: datetime | None = None
    pabellon: str | None = Field(default=None, max_length=200)
    competicion: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(
        default=None, pattern="^(programado|aplazado|jugado|no_disputado)$"
    )


class PartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_partido: uuid.UUID
    id_equipo_local: uuid.UUID | None = None
    id_equipo_visitante: uuid.UUID | None = None
    id_equipo: uuid.UUID | None = None
    id_rival: uuid.UUID | None = None
    es_local: bool | None = None
    id_temporada: uuid.UUID
    fecha: datetime
    jornada: int | None = None
    pabellon: str | None = None
    competicion: str | None = None
    goles_local: int
    goles_visitante: int
    estado: str = "programado"
    equipo_local_nombre: str | None = None
    equipo_visitante_nombre: str | None = None
    temporada_nombre: str | None = None
    temporada_estado: str | None = None


class RivalCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)


class RivalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_rival: uuid.UUID
    id_equipo: uuid.UUID
    nombre: str


class EstadisticaJugadorCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    minutos_jugados: int = Field(default=0, ge=0, le=60)
    goles: int = Field(default=0, ge=0)
    lanzamientos: int = Field(default=0, ge=0)
    lanzamientos_fallados: int = Field(default=0, ge=0)
    asistencias: int = Field(default=0, ge=0)
    perdidas: int = Field(default=0, ge=0)
    recuperaciones: int = Field(default=0, ge=0)
    faltas_cometidas: int = Field(default=0, ge=0)
    faltas_recibidas: int = Field(default=0, ge=0)
    amarillas: int = Field(default=0, ge=0)
    exclusiones_2min: int = Field(default=0, ge=0)
    rojas: int = Field(default=0, ge=0)


class EstadisticaJugadorOut(EstadisticaJugadorCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


class EstadisticaLanzamientoCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    lanzamientos_6m: int = Field(default=0, ge=0)
    goles_6m: int = Field(default=0, ge=0)
    lanzamientos_9m: int = Field(default=0, ge=0)
    goles_9m: int = Field(default=0, ge=0)
    lanzamientos_7m: int = Field(default=0, ge=0)
    goles_7m: int = Field(default=0, ge=0)
    lanzamientos_extremo: int = Field(default=0, ge=0)
    goles_extremo: int = Field(default=0, ge=0)
    lanzamientos_contraataque: int = Field(default=0, ge=0)
    goles_contraataque: int = Field(default=0, ge=0)


class EstadisticaLanzamientoOut(EstadisticaLanzamientoCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


class EstadisticaPorteroCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    minutos_jugados: int = Field(default=0, ge=0, le=60)
    lanzamientos_recibidos: int = Field(default=0, ge=0)
    paradas: int = Field(default=0, ge=0)
    goles_recibidos: int = Field(default=0, ge=0)
    lanzamientos_6m: int = Field(default=0, ge=0)
    paradas_6m: int = Field(default=0, ge=0)
    goles_6m: int = Field(default=0, ge=0)
    lanzamientos_9m: int = Field(default=0, ge=0)
    paradas_9m: int = Field(default=0, ge=0)
    goles_9m: int = Field(default=0, ge=0)
    lanzamientos_7m: int = Field(default=0, ge=0)
    paradas_7m: int = Field(default=0, ge=0)
    goles_7m: int = Field(default=0, ge=0)
    lanzamientos_extremo: int = Field(default=0, ge=0)
    paradas_extremo: int = Field(default=0, ge=0)
    goles_extremo: int = Field(default=0, ge=0)
    lanzamientos_contraataque: int = Field(default=0, ge=0)
    paradas_contraataque: int = Field(default=0, ge=0)
    goles_contraataque: int = Field(default=0, ge=0)


class EstadisticaPorteroOut(EstadisticaPorteroCreate):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: uuid.UUID


class AccionCreate(BaseModel):
    id_partido: uuid.UUID
    id_jugador: uuid.UUID
    id_tipo_accion: int
    minuto: int = Field(ge=0, le=80)
    segundo: int = Field(default=0, ge=0, le=59)
    zona: str | None = Field(default=None, max_length=50)


class AccionOut(AccionCreate):
    model_config = ConfigDict(from_attributes=True)

    id_accion: uuid.UUID


class ResumenJugador(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    partidos: int
    goles: int
    asistencias: int
    lanzamientos: int
    exclusiones_2min: int
    minutos_jugados: int


class LoginIn(BaseModel):
    correo: str
    password: str


class AuthOut(BaseModel):
    token: str
    equipo: EquipoOut


class RegistroIn(BaseModel):
    correo: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    nombre: str = Field(min_length=1, max_length=150)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    img_escudo: str | None = Field(default=None, max_length=255)
    temporada_nombre: str = Field(default="2025/26", max_length=100)
    temporada_inicio: date | None = None
    temporada_fin: date | None = None


class DashboardOut(BaseModel):
    equipo_nombre: str
    partidos_jugados: int
    goles_totales: int
    efectividad: float
    perdidas: int
    efectividad_por_posicion: list[dict]
    ultimos_partidos: list[PartidoOut]
    proximos_partidos: list[PartidoOut]


class JugadorDetalleOut(BaseModel):
    jugador: JugadorOut
    goles: int
    lanzamientos: int
    efectividad: float
    asistencias: int
    minutos_jugados: int
    partidos: int
    es_portero: bool = False
    paradas: int = 0
    lanzamientos_recibidos: int = 0
    efectividad_paradas: float = 0.0
    goles_por_partido: list[dict]
    zonas: dict
    mapa_paradas: dict = {}
    ultimos_partidos: list[dict] = []


class ConvocatoriaItemIn(BaseModel):
    id_jugador: uuid.UUID
    rol: str = Field(default="convocado", pattern="^(convocado|titular|banquillo)$")


class ConvocatoriaItemOut(BaseModel):
    id_jugador: uuid.UUID
    rol: str
    nombre: str | None = None
    apellido: str | None = None
    dorsal: int | None = None
    posiciones: list[str] = []


class ConvocatoriaOut(BaseModel):
    id_partido: uuid.UUID
    items: list[ConvocatoriaItemOut]
    confirmada: bool = False


class ConvocatoriaPut(BaseModel):
    items: list[ConvocatoriaItemIn]
    confirmada: bool = False


class MiembroCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    correo: str = Field(min_length=5, max_length=255)
    cargo: str = Field(default="Staff", max_length=100)
    permiso: str = Field(default="editor", pattern="^(administrador|editor|lector)$")
    estado: str = Field(default="pendiente", pattern="^(activo|pendiente|baja)$")


class MiembroUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    permiso: str | None = Field(default=None, pattern="^(administrador|editor|lector)$")
    estado: str | None = Field(default=None, pattern="^(activo|pendiente|baja)$")


class MiembroOut(BaseModel):
    id_miembro: uuid.UUID
    id_equipo: uuid.UUID
    nombre: str
    correo: str
    cargo: str
    permiso: str
    estado: str

    model_config = ConfigDict(from_attributes=True)
