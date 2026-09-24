import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Equipo(Base):
    __tablename__ = "equipo"

    id_equipo: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    correo: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    datos: Mapped["DatosEquipo | None"] = relationship(
        back_populates="equipo", uselist=False, cascade="all, delete-orphan"
    )
    jugadores_equipo: Mapped[list["JugadorEquipo"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    temporadas: Mapped[list["EquipoTemporada"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    partidos_local: Mapped[list["Partido"]] = relationship(
        back_populates="equipo_local", foreign_keys="Partido.id_equipo_local"
    )
    partidos_visitante: Mapped[list["Partido"]] = relationship(
        back_populates="equipo_visitante", foreign_keys="Partido.id_equipo_visitante"
    )
    miembros: Mapped[list["MiembroClub"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    rivales: Mapped[list["Rival"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    temporadas_propias: Mapped[list["Temporada"]] = relationship(
        back_populates="equipo_owner", foreign_keys="Temporada.id_equipo"
    )
    alineaciones: Mapped[list["AlineacionPlantilla"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    jugadas: Mapped[list["Jugada"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    preparaciones_fisicas: Mapped[list["PreparacionFisica"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    cuota_configs: Mapped[list["CuotaConfig"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    cuota_mensuales: Mapped[list["CuotaMensual"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )
    federacion_pagos: Mapped[list["FederacionPago"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )


class DatosEquipo(Base):
    __tablename__ = "datos_equipo"

    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nombre_corto: Mapped[str | None] = mapped_column(String(80))
    entrenador_nombre: Mapped[str | None] = mapped_column(String(150))
    codigo_federativo: Mapped[str | None] = mapped_column(String(40))
    categoria: Mapped[str | None] = mapped_column(String(100))
    competicion: Mapped[str | None] = mapped_column(String(100))
    pabellon: Mapped[str | None] = mapped_column(String(200))
    img_escudo: Mapped[str | None] = mapped_column(String(255))

    equipo: Mapped["Equipo"] = relationship(back_populates="datos")


class Temporada(Base):
    __tablename__ = "temporada"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('activa', 'cerrada', 'archivada')",
            name="ck_temporada_estado",
        ),
    )

    id_temporada: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    equipo_owner: Mapped["Equipo | None"] = relationship(
        back_populates="temporadas_propias", foreign_keys=[id_equipo]
    )
    equipos: Mapped[list["EquipoTemporada"]] = relationship(
        back_populates="temporada", cascade="all, delete-orphan"
    )
    partidos: Mapped[list["Partido"]] = relationship(
        back_populates="temporada", passive_deletes=True
    )


class Rival(Base):
    __tablename__ = "rival"

    id_rival: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)

    equipo: Mapped["Equipo"] = relationship(back_populates="rivales")
    partidos: Mapped[list["Partido"]] = relationship(back_populates="rival")
    jugadoras: Mapped[list["RivalJugador"]] = relationship(
        back_populates="rival", cascade="all, delete-orphan"
    )


class RivalJugador(Base):
    """Plantilla ligera del rival (dorsales reutilizables entre partidos)."""

    __tablename__ = "rival_jugador"
    __table_args__ = (
        UniqueConstraint("id_rival", "dorsal", name="uq_rival_jugador_dorsal"),
    )

    id_rival_jugador: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_rival: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rival.id_rival", ondelete="CASCADE"), nullable=False, index=True
    )
    dorsal: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    rival: Mapped["Rival"] = relationship(back_populates="jugadoras")
    acciones: Mapped[list["Accion"]] = relationship(back_populates="rival_jugador")


class EquipoTemporada(Base):
    __tablename__ = "equipo_temporada"

    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), primary_key=True
    )
    id_temporada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("temporada.id_temporada", ondelete="CASCADE"), primary_key=True
    )
    categoria: Mapped[str | None] = mapped_column(String(100))
    competicion: Mapped[str | None] = mapped_column(String(100))

    equipo: Mapped["Equipo"] = relationship(back_populates="temporadas")
    temporada: Mapped["Temporada"] = relationship(back_populates="equipos")


class Jugador(Base):
    __tablename__ = "jugador"

    id_jugador: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    altura_cm: Mapped[int | None] = mapped_column(Integer)
    peso_kg: Mapped[int | None] = mapped_column(Integer)
    img_foto: Mapped[str | None] = mapped_column(String(255))

    equipos: Mapped[list["JugadorEquipo"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )
    posiciones: Mapped[list["JugadorPosicion"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )
    estadisticas: Mapped[list["EstadisticaJugador"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )
    estadisticas_lanzamiento: Mapped[list["EstadisticaLanzamiento"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )
    estadisticas_portero: Mapped[list["EstadisticaPortero"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )
    acciones: Mapped[list["Accion"]] = relationship(
        back_populates="jugador", cascade="all, delete-orphan"
    )


class JugadorEquipo(Base):
    __tablename__ = "jugador_equipo"
    __table_args__ = (
        CheckConstraint(
            "fecha_baja IS NULL OR fecha_alta IS NULL OR fecha_baja >= fecha_alta",
            name="ck_jugador_equipo_fechas",
        ),
    )

    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), primary_key=True
    )
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), primary_key=True
    )
    dorsal: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_alta: Mapped[date | None] = mapped_column(Date)
    fecha_baja: Mapped[date | None] = mapped_column(Date)

    jugador: Mapped["Jugador"] = relationship(back_populates="equipos")
    equipo: Mapped["Equipo"] = relationship(back_populates="jugadores_equipo")


class Posicion(Base):
    __tablename__ = "posicion"

    id_posicion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    jugadores: Mapped[list["JugadorPosicion"]] = relationship(back_populates="posicion")


class JugadorPosicion(Base):
    __tablename__ = "jugador_posicion"

    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), primary_key=True
    )
    id_posicion: Mapped[int] = mapped_column(
        Integer, ForeignKey("posicion.id_posicion", ondelete="CASCADE"), primary_key=True
    )

    jugador: Mapped["Jugador"] = relationship(back_populates="posiciones")
    posicion: Mapped["Posicion"] = relationship(back_populates="jugadores")


class Partido(Base):
    __tablename__ = "partido"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('programado', 'aplazado', 'jugado', 'no_disputado')",
            name="ck_partido_estado",
        ),
    )

    id_partido: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Dueño del partido (club autenticado)
    id_equipo: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=True, index=True
    )
    id_rival: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("rival.id_rival", ondelete="RESTRICT"), nullable=True, index=True
    )
    es_local: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    # Legacy: partidos antiguos con dos equipos reales
    id_equipo_local: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="RESTRICT"), nullable=True
    )
    id_equipo_visitante: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="RESTRICT"), nullable=True
    )
    id_temporada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("temporada.id_temporada", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    jornada: Mapped[int | None] = mapped_column(Integer)
    pabellon: Mapped[str | None] = mapped_column(String(200))
    competicion: Mapped[str | None] = mapped_column(String(100))
    img_portada: Mapped[str | None] = mapped_column(String(255))
    goles_local: Mapped[int] = mapped_column(Integer, default=0)
    goles_visitante: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="programado")

    equipo_owner: Mapped["Equipo | None"] = relationship(
        foreign_keys=[id_equipo],
    )
    rival: Mapped["Rival | None"] = relationship(back_populates="partidos")
    equipo_local: Mapped["Equipo | None"] = relationship(
        back_populates="partidos_local", foreign_keys=[id_equipo_local]
    )
    equipo_visitante: Mapped["Equipo | None"] = relationship(
        back_populates="partidos_visitante", foreign_keys=[id_equipo_visitante]
    )
    temporada: Mapped["Temporada"] = relationship(back_populates="partidos")
    estadisticas_jugador: Mapped[list["EstadisticaJugador"]] = relationship(
        back_populates="partido", cascade="all, delete-orphan"
    )
    estadisticas_lanzamiento: Mapped[list["EstadisticaLanzamiento"]] = relationship(
        back_populates="partido", cascade="all, delete-orphan"
    )
    estadisticas_portero: Mapped[list["EstadisticaPortero"]] = relationship(
        back_populates="partido", cascade="all, delete-orphan"
    )
    acciones: Mapped[list["Accion"]] = relationship(
        back_populates="partido", cascade="all, delete-orphan"
    )
    convocatoria: Mapped[list["Convocatoria"]] = relationship(
        back_populates="partido", cascade="all, delete-orphan"
    )


class Convocatoria(Base):
    __tablename__ = "convocatoria"
    __table_args__ = (
        UniqueConstraint("id_partido", "id_jugador", name="uq_convocatoria_partido_jugador"),
        CheckConstraint(
            "rol IN ('convocado', 'titular', 'banquillo')",
            name="ck_convocatoria_rol",
        ),
    )

    id_convocatoria: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_partido: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partido.id_partido", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="convocado")
    zona_campo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    zona_ataque: Mapped[str | None] = mapped_column(String(30), nullable=True)
    zona_defensa: Mapped[str | None] = mapped_column(String(30), nullable=True)

    partido: Mapped["Partido"] = relationship(back_populates="convocatoria")
    jugador: Mapped["Jugador"] = relationship()


class AlineacionPlantilla(Base):
    __tablename__ = "alineacion_plantilla"

    id_alineacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="ataque")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    equipo: Mapped["Equipo"] = relationship(back_populates="alineaciones")
    items: Mapped[list["AlineacionPlantillaItem"]] = relationship(
        back_populates="plantilla", cascade="all, delete-orphan"
    )


class AlineacionPlantillaItem(Base):
    __tablename__ = "alineacion_plantilla_item"
    __table_args__ = (
        UniqueConstraint("id_alineacion", "zona_campo", name="uq_alineacion_zona"),
        UniqueConstraint("id_alineacion", "id_jugador", name="uq_alineacion_jugador"),
    )

    id_item: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_alineacion: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alineacion_plantilla.id_alineacion", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    zona_campo: Mapped[str] = mapped_column(String(30), nullable=False)

    plantilla: Mapped["AlineacionPlantilla"] = relationship(back_populates="items")
    jugador: Mapped["Jugador"] = relationship()


class EstadisticaJugador(Base):
    __tablename__ = "estadistica_jugador"
    __table_args__ = (
        UniqueConstraint("id_partido", "id_jugador", name="uq_estadistica_jugador_partido"),
    )

    id_estadistica: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_partido: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partido.id_partido", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    minutos_jugados: Mapped[int] = mapped_column(Integer, default=0)
    goles: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_fallados: Mapped[int] = mapped_column(Integer, default=0)
    asistencias: Mapped[int] = mapped_column(Integer, default=0)
    perdidas: Mapped[int] = mapped_column(Integer, default=0)
    recuperaciones: Mapped[int] = mapped_column(Integer, default=0)
    faltas_cometidas: Mapped[int] = mapped_column(Integer, default=0)
    faltas_recibidas: Mapped[int] = mapped_column(Integer, default=0)
    amarillas: Mapped[int] = mapped_column(Integer, default=0)
    exclusiones_2min: Mapped[int] = mapped_column(Integer, default=0)
    rojas: Mapped[int] = mapped_column(Integer, default=0)
    azules: Mapped[int] = mapped_column(Integer, default=0)

    partido: Mapped["Partido"] = relationship(back_populates="estadisticas_jugador")
    jugador: Mapped["Jugador"] = relationship(back_populates="estadisticas")


class EstadisticaLanzamiento(Base):
    __tablename__ = "estadistica_lanzamiento"
    __table_args__ = (
        UniqueConstraint("id_partido", "id_jugador", name="uq_estadistica_lanzamiento_partido"),
    )

    id_estadistica: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_partido: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partido.id_partido", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    lanzamientos_6m: Mapped[int] = mapped_column(Integer, default=0)
    goles_6m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_9m: Mapped[int] = mapped_column(Integer, default=0)
    goles_9m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_7m: Mapped[int] = mapped_column(Integer, default=0)
    goles_7m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_extremo: Mapped[int] = mapped_column(Integer, default=0)
    goles_extremo: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_contraataque: Mapped[int] = mapped_column(Integer, default=0)
    goles_contraataque: Mapped[int] = mapped_column(Integer, default=0)

    partido: Mapped["Partido"] = relationship(back_populates="estadisticas_lanzamiento")
    jugador: Mapped["Jugador"] = relationship(back_populates="estadisticas_lanzamiento")


class EstadisticaPortero(Base):
    __tablename__ = "estadistica_portero"
    __table_args__ = (
        UniqueConstraint("id_partido", "id_jugador", name="uq_estadistica_portero_partido"),
    )

    id_estadistica: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_partido: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partido.id_partido", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    minutos_jugados: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_recibidos: Mapped[int] = mapped_column(Integer, default=0)
    paradas: Mapped[int] = mapped_column(Integer, default=0)
    goles_recibidos: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_6m: Mapped[int] = mapped_column(Integer, default=0)
    paradas_6m: Mapped[int] = mapped_column(Integer, default=0)
    goles_6m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_9m: Mapped[int] = mapped_column(Integer, default=0)
    paradas_9m: Mapped[int] = mapped_column(Integer, default=0)
    goles_9m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_7m: Mapped[int] = mapped_column(Integer, default=0)
    paradas_7m: Mapped[int] = mapped_column(Integer, default=0)
    goles_7m: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_extremo: Mapped[int] = mapped_column(Integer, default=0)
    paradas_extremo: Mapped[int] = mapped_column(Integer, default=0)
    goles_extremo: Mapped[int] = mapped_column(Integer, default=0)
    lanzamientos_contraataque: Mapped[int] = mapped_column(Integer, default=0)
    paradas_contraataque: Mapped[int] = mapped_column(Integer, default=0)
    goles_contraataque: Mapped[int] = mapped_column(Integer, default=0)

    partido: Mapped["Partido"] = relationship(back_populates="estadisticas_portero")
    jugador: Mapped["Jugador"] = relationship(back_populates="estadisticas_portero")


class TipoAccion(Base):
    __tablename__ = "tipo_accion"

    id_tipo_accion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    acciones: Mapped[list["Accion"]] = relationship(back_populates="tipo_accion")


class Accion(Base):
    __tablename__ = "accion"

    id_accion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_partido: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partido.id_partido", ondelete="CASCADE"), nullable=False
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False
    )
    id_tipo_accion: Mapped[int] = mapped_column(
        Integer, ForeignKey("tipo_accion.id_tipo_accion", ondelete="RESTRICT"), nullable=False
    )
    minuto: Mapped[int] = mapped_column(Integer, nullable=False)
    segundo: Mapped[int] = mapped_column(Integer, default=0)
    zona: Mapped[str | None] = mapped_column(String(50))
    zona_porteria: Mapped[str | None] = mapped_column(String(50))
    es_contraataque: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    id_rival_jugador: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("rival_jugador.id_rival_jugador", ondelete="SET NULL"), nullable=True
    )

    partido: Mapped["Partido"] = relationship(back_populates="acciones")
    jugador: Mapped["Jugador"] = relationship(back_populates="acciones")
    tipo_accion: Mapped["TipoAccion"] = relationship(back_populates="acciones")
    rival_jugador: Mapped["RivalJugador | None"] = relationship(back_populates="acciones")


class MiembroClub(Base):
    __tablename__ = "miembro_club"
    __table_args__ = (
        CheckConstraint(
            "permiso IN ('administrador', 'miembro')",
            name="ck_miembro_permiso",
        ),
        CheckConstraint(
            "estado IN ('activo', 'pendiente', 'baja')",
            name="ck_miembro_estado",
        ),
        UniqueConstraint("id_equipo", "correo", name="uq_miembro_equipo_correo"),
    )

    id_miembro: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    correo: Mapped[str] = mapped_column(String(255), nullable=False)
    cargo: Mapped[str] = mapped_column(String(100), nullable=False, default="Staff")
    permiso: Mapped[str] = mapped_column(String(20), nullable=False, default="miembro")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    invite_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    equipo: Mapped["Equipo"] = relationship(back_populates="miembros")


class Jugada(Base):
    __tablename__ = "jugada"
    __table_args__ = (
        CheckConstraint(
            "fase IN ('ataque', 'defensa', 'completo')",
            name="ck_jugada_fase",
        ),
        CheckConstraint(
            "ambito IN ('tactica', 'fisico')",
            name="ck_jugada_ambito",
        ),
    )

    id_jugada: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    fase: Mapped[str] = mapped_column(String(20), nullable=False, default="ataque")
    ambito: Mapped[str] = mapped_column(String(20), nullable=False, default="tactica")
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    equipo: Mapped["Equipo"] = relationship(back_populates="jugadas")
    piezas: Mapped[list["JugadaPieza"]] = relationship(
        back_populates="jugada", cascade="all, delete-orphan", order_by="JugadaPieza.orden"
    )
    pasos: Mapped[list["JugadaPaso"]] = relationship(
        back_populates="jugada", cascade="all, delete-orphan", order_by="JugadaPaso.orden"
    )


class JugadaPieza(Base):
    __tablename__ = "jugada_pieza"

    id_pieza: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_jugada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada.id_jugada", ondelete="CASCADE"), nullable=False, index=True
    )
    etiqueta: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    id_jugador: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="SET NULL"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    jugada: Mapped["Jugada"] = relationship(back_populates="piezas")


class JugadaPaso(Base):
    __tablename__ = "jugada_paso"
    __table_args__ = (
        UniqueConstraint("id_jugada", "orden", name="uq_jugada_paso_orden"),
    )

    id_paso: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_jugada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada.id_jugada", ondelete="CASCADE"), nullable=False, index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    titulo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    balon_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    balon_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    id_pieza_balon: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("jugada_pieza.id_pieza", ondelete="SET NULL"), nullable=True
    )

    jugada: Mapped["Jugada"] = relationship(back_populates="pasos")
    posiciones: Mapped[list["JugadaPosicion"]] = relationship(
        back_populates="paso", cascade="all, delete-orphan"
    )
    flechas: Mapped[list["JugadaFlecha"]] = relationship(
        back_populates="paso", cascade="all, delete-orphan"
    )


class JugadaPosicion(Base):
    __tablename__ = "jugada_posicion"
    __table_args__ = (
        UniqueConstraint("id_paso", "id_pieza", name="uq_jugada_posicion_pieza"),
    )

    id_posicion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_paso: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada_paso.id_paso", ondelete="CASCADE"), nullable=False, index=True
    )
    id_pieza: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada_pieza.id_pieza", ondelete="CASCADE"), nullable=False
    )
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)

    paso: Mapped["JugadaPaso"] = relationship(back_populates="posiciones")


class JugadaFlecha(Base):
    __tablename__ = "jugada_flecha"

    id_flecha: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_paso: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada_paso.id_paso", ondelete="CASCADE"), nullable=False, index=True
    )
    id_pieza: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugada_pieza.id_pieza", ondelete="CASCADE"), nullable=False
    )
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="movimiento")

    paso: Mapped["JugadaPaso"] = relationship(back_populates="flechas")


PREPARACION_TIPOS = (
    "fuerza",
    "resistencia",
    "potencia",
    "movilidad",
    "prevencion",
    "prepartido",
    "recuperacion",
    "otro",
)

PREPARACION_INTENSIDADES = ("baja", "media", "alta")


class PreparacionFisica(Base):
    """Sesión / plan de preparación física del equipo (sin PDF por ahora)."""

    __tablename__ = "preparacion_fisica"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('fuerza', 'resistencia', 'potencia', 'movilidad', 'prevencion', "
            "'prepartido', 'recuperacion', 'otro')",
            name="ck_preparacion_fisica_tipo",
        ),
        CheckConstraint(
            "intensidad IS NULL OR intensidad IN ('baja', 'media', 'alta')",
            name="ck_preparacion_fisica_intensidad",
        ),
    )

    id_preparacion: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, default="fuerza")
    objetivo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contenido: Mapped[str | None] = mapped_column(Text, nullable=True)
    duracion_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intensidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    equipo: Mapped["Equipo"] = relationship(back_populates="preparaciones_fisicas")


# Meses de cuota: septiembre (9) → junio (6). Un pago por mes y temporada.
CUOTA_MESES = (9, 10, 11, 12, 1, 2, 3, 4, 5, 6)


class CuotaConfig(Base):
    """Importe de cuota mensual y federación por equipo/temporada."""

    __tablename__ = "cuota_config"
    __table_args__ = (
        UniqueConstraint("id_equipo", "id_temporada", name="uq_cuota_config_equipo_temp"),
    )

    id_config: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    id_temporada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("temporada.id_temporada", ondelete="CASCADE"), nullable=False, index=True
    )
    importe_mensual: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    importe_federacion: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    equipo: Mapped["Equipo"] = relationship(back_populates="cuota_configs")
    temporada: Mapped["Temporada"] = relationship()


class CuotaMensual(Base):
    """Pago mensual de cuota (sep–jun) por jugadora."""

    __tablename__ = "cuota_mensual"
    __table_args__ = (
        UniqueConstraint(
            "id_equipo", "id_temporada", "id_jugador", "mes",
            name="uq_cuota_mensual_jugador_mes",
        ),
        CheckConstraint("mes IN (1,2,3,4,5,6,9,10,11,12)", name="ck_cuota_mensual_mes"),
    )

    id_pago: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    id_temporada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("temporada.id_temporada", ondelete="CASCADE"), nullable=False, index=True
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False, index=True
    )
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    pagado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pagado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    equipo: Mapped["Equipo"] = relationship(back_populates="cuota_mensuales")
    jugador: Mapped["Jugador"] = relationship()
    temporada: Mapped["Temporada"] = relationship()


class FederacionPago(Base):
    """Licencia federativa: pago único por temporada (sin prorrateo)."""

    __tablename__ = "federacion_pago"
    __table_args__ = (
        UniqueConstraint(
            "id_equipo", "id_temporada", "id_jugador",
            name="uq_federacion_jugador_temp",
        ),
    )

    id_pago: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    id_temporada: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("temporada.id_temporada", ondelete="CASCADE"), nullable=False, index=True
    )
    id_jugador: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jugador.id_jugador", ondelete="CASCADE"), nullable=False, index=True
    )
    pagado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pagado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    equipo: Mapped["Equipo"] = relationship(back_populates="federacion_pagos")
    jugador: Mapped["Jugador"] = relationship()
    temporada: Mapped["Temporada"] = relationship()
