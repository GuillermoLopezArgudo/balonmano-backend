import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
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
    partidos: Mapped[list["Partido"]] = relationship(back_populates="temporada")


class Rival(Base):
    __tablename__ = "rival"

    id_rival: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipo.id_equipo", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)

    equipo: Mapped["Equipo"] = relationship(back_populates="rivales")
    partidos: Mapped[list["Partido"]] = relationship(back_populates="rival")


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

    partido: Mapped["Partido"] = relationship(back_populates="convocatoria")
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

    partido: Mapped["Partido"] = relationship(back_populates="acciones")
    jugador: Mapped["Jugador"] = relationship(back_populates="acciones")
    tipo_accion: Mapped["TipoAccion"] = relationship(back_populates="acciones")


class MiembroClub(Base):
    __tablename__ = "miembro_club"
    __table_args__ = (
        CheckConstraint(
            "permiso IN ('administrador', 'editor', 'lector')",
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
    permiso: Mapped[str] = mapped_column(String(20), nullable=False, default="editor")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    equipo: Mapped["Equipo"] = relationship(back_populates="miembros")
