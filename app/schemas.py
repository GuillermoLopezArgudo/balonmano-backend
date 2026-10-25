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
    img_portada: str | None = Field(default=None, max_length=255)
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
    img_portada: str | None = Field(default=None, max_length=255)
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
    img_portada: str | None = None
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


class RivalJugadorCreate(BaseModel):
    dorsal: int = Field(ge=0, le=99)
    nombre: str | None = Field(default=None, max_length=120)


class RivalJugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_rival_jugador: uuid.UUID
    id_rival: uuid.UUID
    dorsal: int
    nombre: str | None = None
    activo: bool = True


class RivalGoleadoraOut(BaseModel):
    id_rival_jugador: uuid.UUID | None = None
    dorsal: int | None = None
    nombre: str | None = None
    goles: int
    zona_top: str | None = None
    zona_top_label: str | None = None
    zonas: dict[str, int] = {}


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
    azules: int = Field(default=0, ge=0)


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
    zona_porteria: str | None = Field(default=None, max_length=50)
    es_contraataque: bool = False
    id_rival_jugador: uuid.UUID | None = None


class AccionUpdate(BaseModel):
    id_jugador: uuid.UUID | None = None
    id_tipo_accion: int | None = None
    minuto: int | None = Field(default=None, ge=0, le=80)
    segundo: int | None = Field(default=None, ge=0, le=59)
    zona: str | None = Field(default=None, max_length=50)
    zona_porteria: str | None = Field(default=None, max_length=50)
    es_contraataque: bool | None = None
    id_rival_jugador: uuid.UUID | None = None


class AccionOut(AccionCreate):
    model_config = ConfigDict(from_attributes=True)

    id_accion: uuid.UUID
    rival_dorsal: int | None = None
    rival_nombre: str | None = None


class ResumenJugador(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    partidos: int
    goles: int
    asistencias: int
    lanzamientos: int
    perdidas: int = 0
    amarillas: int = 0
    exclusiones_2min: int = 0
    rojas: int = 0
    azules: int = 0
    minutos_jugados: int
    pct_perdidas: float = 0.0


class LoginIn(BaseModel):
    correo: str
    password: str


class MiembroSesionOut(BaseModel):
    id_miembro: uuid.UUID
    nombre: str
    correo: str
    cargo: str
    permiso: str


class AuthOut(BaseModel):
    token: str
    equipo: EquipoOut
    miembro: MiembroSesionOut | None = None


class SesionOut(BaseModel):
    equipo: EquipoOut
    miembro: MiembroSesionOut | None = None
    permiso: str = "administrador"


class PasswordChangeIn(BaseModel):
    password_actual: str = Field(min_length=1, max_length=128)
    password_nueva: str = Field(min_length=8, max_length=128)


class MiembroPerfilUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)


class AceptarInvitacionIn(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    nombre: str | None = Field(default=None, min_length=2, max_length=150)


class InvitacionInfoOut(BaseModel):
    nombre: str
    correo: str
    cargo: str
    permiso: str
    club: str
    expira: datetime | None = None
    ya_aceptada: bool = False


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
    perdidas: int = 0
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


ZONA_CAMPO_PATTERN = (
    "^(portero|extremo_izq|lateral_izq|central|lateral_der|extremo_der|pivote)$"
)


class ConvocatoriaItemIn(BaseModel):
    id_jugador: uuid.UUID
    rol: str = Field(default="convocado", pattern="^(convocado|titular|banquillo)$")
    zona_campo: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)
    zona_ataque: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)
    zona_defensa: str | None = Field(default=None, pattern=ZONA_CAMPO_PATTERN)


class ConvocatoriaItemOut(BaseModel):
    id_jugador: uuid.UUID
    rol: str
    zona_campo: str | None = None
    zona_ataque: str | None = None
    zona_defensa: str | None = None
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


class AlineacionItemIn(BaseModel):
    id_jugador: uuid.UUID
    zona_campo: str = Field(pattern=ZONA_CAMPO_PATTERN)


class AlineacionItemOut(BaseModel):
    id_jugador: uuid.UUID
    zona_campo: str
    nombre: str | None = None
    apellido: str | None = None
    dorsal: int | None = None
    posiciones: list[str] = []


class AlineacionCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="ataque", pattern="^(ataque|defensa)$")
    items: list[AlineacionItemIn] = []


class AlineacionUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern="^(ataque|defensa)$")
    items: list[AlineacionItemIn] | None = None


class AlineacionOut(BaseModel):
    id_alineacion: uuid.UUID
    nombre: str
    tipo: str = "ataque"
    creado_en: datetime
    actualizado_en: datetime
    items: list[AlineacionItemOut] = []


class MiembroCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    correo: str = Field(min_length=5, max_length=255)
    cargo: str = Field(default="Staff", max_length=100)
    estado: str = Field(default="pendiente", pattern="^(activo|pendiente|baja)$")


class MiembroUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, pattern="^(activo|pendiente|baja)$")


class MiembroOut(BaseModel):
    id_miembro: uuid.UUID
    id_equipo: uuid.UUID
    nombre: str
    correo: str
    cargo: str
    permiso: str
    estado: str
    tiene_acceso: bool = False
    invite_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ——— Jugadas (pizarra multipaso) ———


class JugadaPosicionIn(BaseModel):
    id_pieza: uuid.UUID
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class JugadaFlechaIn(BaseModel):
    id_pieza: uuid.UUID
    x1: float = Field(ge=0, le=100)
    y1: float = Field(ge=0, le=100)
    x2: float = Field(ge=0, le=100)
    y2: float = Field(ge=0, le=100)
    tipo: str = Field(default="movimiento", pattern="^(movimiento|pase|lanzamiento)$")


class JugadaPiezaIn(BaseModel):
    id_pieza: uuid.UUID | None = None
    etiqueta: str = Field(min_length=1, max_length=40)
    color: str | None = Field(default=None, max_length=20)
    id_jugador: uuid.UUID | None = None
    orden: int = Field(default=0, ge=0, le=30)


class JugadaPasoIn(BaseModel):
    id_paso: uuid.UUID | None = None
    orden: int = Field(ge=0, le=200)
    titulo: str | None = Field(default=None, max_length=80)
    balon_x: float | None = Field(default=None, ge=0, le=100)
    balon_y: float | None = Field(default=None, ge=0, le=100)
    id_pieza_balon: uuid.UUID | None = None
    posiciones: list[JugadaPosicionIn] = []
    flechas: list[JugadaFlechaIn] = []


class JugadaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    fase: str = Field(default="ataque", pattern="^(ataque|defensa|completo)$")
    ambito: str = Field(default="tactica", pattern="^(tactica|fisico)$")
    descripcion: str | None = Field(default=None, max_length=4000)
    piezas: list[JugadaPiezaIn] = []
    pasos: list[JugadaPasoIn] = []


class JugadaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    fase: str | None = Field(default=None, pattern="^(ataque|defensa|completo)$")
    ambito: str | None = Field(default=None, pattern="^(tactica|fisico)$")
    descripcion: str | None = Field(default=None, max_length=4000)
    piezas: list[JugadaPiezaIn] | None = None
    pasos: list[JugadaPasoIn] | None = None


class JugadaPosicionOut(BaseModel):
    id_pieza: uuid.UUID
    x: float
    y: float


class JugadaFlechaOut(BaseModel):
    id_flecha: uuid.UUID
    id_pieza: uuid.UUID
    x1: float
    y1: float
    x2: float
    y2: float
    tipo: str = "movimiento"


class JugadaPiezaOut(BaseModel):
    id_pieza: uuid.UUID
    etiqueta: str
    color: str | None = None
    id_jugador: uuid.UUID | None = None
    orden: int = 0


class JugadaPasoOut(BaseModel):
    id_paso: uuid.UUID
    orden: int
    titulo: str | None = None
    balon_x: float | None = None
    balon_y: float | None = None
    id_pieza_balon: uuid.UUID | None = None
    posiciones: list[JugadaPosicionOut] = []
    flechas: list[JugadaFlechaOut] = []


class JugadaListOut(BaseModel):
    id_jugada: uuid.UUID
    nombre: str
    fase: str
    ambito: str = "tactica"
    descripcion: str | None = None
    num_pasos: int = 0
    num_piezas: int = 0
    creado_en: datetime
    actualizado_en: datetime


class JugadaOut(BaseModel):
    id_jugada: uuid.UUID
    nombre: str
    fase: str
    ambito: str = "tactica"
    descripcion: str | None = None
    creado_en: datetime
    actualizado_en: datetime
    piezas: list[JugadaPiezaOut] = []
    pasos: list[JugadaPasoOut] = []


class JugadaCopiarIn(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)


# --- Cuotas / Federación ---

CUOTA_MESES_ORDEN = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


class CuotaConfigIn(BaseModel):
    importe_mensual: float = Field(ge=0, le=99999)
    importe_federacion: float = Field(ge=0, le=99999)


class CuotaConfigOut(BaseModel):
    id_temporada: uuid.UUID
    importe_mensual: float
    importe_federacion: float


class CuotaMesEstado(BaseModel):
    mes: int
    pagado: bool


class CuotaJugadoraOut(BaseModel):
    id_jugador: uuid.UUID
    nombre: str
    apellido: str
    dorsal: int | None = None
    federacion_pagada: bool = False
    meses: list[CuotaMesEstado] = []


class CuotaResumenOut(BaseModel):
    total_jugadoras: int = 0
    federacion_pagadas: int = 0
    federacion_pendientes: int = 0
    cuotas_pagadas: int = 0
    cuotas_pendientes: int = 0
    esperado_mensual: float = 0
    cobrado_mensual: float = 0
    esperado_federacion: float = 0
    cobrado_federacion: float = 0


class CuotasTemporadaOut(BaseModel):
    id_temporada: uuid.UUID
    temporada_nombre: str
    temporada_estado: str
    meses: list[int] = Field(default_factory=lambda: list(CUOTA_MESES_ORDEN))
    config: CuotaConfigOut
    jugadoras: list[CuotaJugadoraOut] = []
    resumen: CuotaResumenOut = Field(default_factory=CuotaResumenOut)
    solo_lectura: bool = False


class CuotaMensualPatch(BaseModel):
    id_jugador: uuid.UUID
    mes: int = Field(ge=1, le=12)
    pagado: bool


class FederacionPatch(BaseModel):
    id_jugador: uuid.UUID
    pagado: bool


class CuotaBulkIn(BaseModel):
    id_jugadores: list[uuid.UUID] = Field(min_length=1)
    accion: str = Field(
        pattern="^(limpiar|federacion_pagada|federacion_pendiente|cuotas_pagadas|cuotas_pendientes)$",
        description="cuotas_pagadas = marcar sep–jun como pagadas en la selección",
    )


# ——— Preparación física ———

_PREP_TIPO = (
    "^(fuerza|resistencia|potencia|movilidad|prevencion|prepartido|recuperacion|otro)$"
)
_PREP_INTENSIDAD = "^(baja|media|alta)$"


class PreparacionFisicaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="fuerza", pattern=_PREP_TIPO)
    objetivo: str | None = Field(default=None, max_length=300)
    contenido: str | None = Field(default=None, max_length=20000)
    duracion_min: int | None = Field(default=None, ge=1, le=600)
    intensidad: str | None = Field(default=None, pattern=_PREP_INTENSIDAD)


class PreparacionFisicaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, pattern=_PREP_TIPO)
    objetivo: str | None = Field(default=None, max_length=300)
    contenido: str | None = Field(default=None, max_length=20000)
    duracion_min: int | None = Field(default=None, ge=1, le=600)
    intensidad: str | None = Field(default=None, pattern=_PREP_INTENSIDAD)


class PreparacionFisicaOut(BaseModel):
    id_preparacion: uuid.UUID
    nombre: str
    tipo: str
    objetivo: str | None = None
    contenido: str | None = None
    duracion_min: int | None = None
    intensidad: str | None = None
    creado_en: datetime
    actualizado_en: datetime
