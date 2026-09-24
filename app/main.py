from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import models  # noqa: F401 — registra modelos en metadata
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers.auth import router as auth_router
from app.routers.alineaciones import router as alineaciones_router
from app.routers.jugadas import router as jugadas_router
from app.routers.preparaciones import router as preparaciones_router
from app.routers.catalogos import router as catalogos_router
from app.routers.convocatorias import router as convocatorias_router
from app.routers.cuotas import router as cuotas_router
from app.routers.dashboard import router as dashboard_router
from app.routers.equipos import router as equipos_router
from app.routers.estadisticas import router as estadisticas_router
from app.routers.jugadores import router as jugadores_router
from app.routers.miembros import router as miembros_router
from app.routers.partidos import router as partidos_router
from app.routers.rivales import router as rivales_router
from app.routers.temporadas import router as temporadas_router
from app.routers.uploads import router as uploads_router
from app.routers.uploads import uploads_root
from app.realtime import set_main_loop
from app.seed import seed_catalogos

logger = logging.getLogger("siete.schema")

# Errores PG que suelen ser idempotentes / ya aplicados
_SAFE_PG_CODES = {
    "42701",  # duplicate_column
    "42P07",  # duplicate_table
    "42710",  # duplicate_object
    "42P16",  # invalid_table_definition (a veces en ALTER ya hecho)
}


def _pg_code(exc: Exception) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is not None and getattr(orig, "pgcode", None):
        return orig.pgcode
    return getattr(exc, "pgcode", None)


def ensure_schema() -> None:
    """Parches incrementales hasta migrar a Alembic. No traga errores silenciosamente."""
    stmts = [
        "ALTER TABLE datos_equipo ADD COLUMN IF NOT EXISTS nombre_corto VARCHAR(80)",
        "ALTER TABLE datos_equipo ADD COLUMN IF NOT EXISTS codigo_federativo VARCHAR(40)",
        "ALTER TABLE datos_equipo ADD COLUMN IF NOT EXISTS pabellon VARCHAR(200)",
        "ALTER TABLE jugador ADD COLUMN IF NOT EXISTS peso_kg INTEGER",
        "ALTER TABLE jugador ADD COLUMN IF NOT EXISTS img_foto VARCHAR(255)",
        "ALTER TABLE accion ADD COLUMN IF NOT EXISTS zona_porteria VARCHAR(50)",
        "ALTER TABLE accion ADD COLUMN IF NOT EXISTS id_rival_jugador UUID",
        "ALTER TABLE convocatoria ADD COLUMN IF NOT EXISTS zona_campo VARCHAR(30)",
        "ALTER TABLE convocatoria ADD COLUMN IF NOT EXISTS zona_ataque VARCHAR(30)",
        "ALTER TABLE convocatoria ADD COLUMN IF NOT EXISTS zona_defensa VARCHAR(30)",
        "ALTER TABLE estadistica_jugador ADD COLUMN IF NOT EXISTS azules INTEGER DEFAULT 0",
        "ALTER TABLE accion ADD COLUMN IF NOT EXISTS es_contraataque BOOLEAN DEFAULT FALSE",
        "ALTER TABLE alineacion_plantilla ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT 'ataque'",
        "ALTER TABLE jugada_paso ADD COLUMN IF NOT EXISTS balon_x DOUBLE PRECISION",
        "ALTER TABLE jugada_paso ADD COLUMN IF NOT EXISTS balon_y DOUBLE PRECISION",
        "ALTER TABLE jugada_paso ADD COLUMN IF NOT EXISTS id_pieza_balon UUID",
        "ALTER TABLE jugada_flecha ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT 'movimiento'",
        "ALTER TABLE jugada ADD COLUMN IF NOT EXISTS ambito VARCHAR(20) DEFAULT 'tactica'",
        """
        UPDATE jugada SET ambito = 'tactica'
        WHERE ambito IS NULL OR ambito = ''
        """,
        """
        DO $$ BEGIN
          ALTER TABLE jugada DROP CONSTRAINT IF EXISTS ck_jugada_fase;
          ALTER TABLE jugada
            ADD CONSTRAINT ck_jugada_fase
            CHECK (fase IN ('ataque', 'defensa', 'completo'));
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """,
        """
        DO $$ BEGIN
          ALTER TABLE jugada DROP CONSTRAINT IF EXISTS ck_jugada_ambito;
          ALTER TABLE jugada
            ADD CONSTRAINT ck_jugada_ambito
            CHECK (ambito IN ('tactica', 'fisico'));
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """,
        """
        UPDATE jugada_flecha SET tipo = 'movimiento'
        WHERE tipo IS NULL OR tipo = ''
        """,
        """
        UPDATE convocatoria SET zona_ataque = zona_campo
        WHERE zona_ataque IS NULL AND zona_campo IS NOT NULL
        """,
        """
        UPDATE alineacion_plantilla SET tipo = 'ataque'
        WHERE tipo IS NULL OR tipo = ''
        """,
        """
        DO $$ BEGIN
          ALTER TABLE accion
            ADD CONSTRAINT fk_accion_rival_jugador
            FOREIGN KEY (id_rival_jugador) REFERENCES rival_jugador(id_rival_jugador)
            ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        WHEN undefined_table THEN NULL;
        END $$;
        """,
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS pabellon VARCHAR(200)",
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS competicion VARCHAR(100)",
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS img_portada VARCHAR(255)",
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'programado'",
        "ALTER TABLE temporada ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'activa'",
        "ALTER TABLE temporada ADD COLUMN IF NOT EXISTS cerrada_en TIMESTAMP",
        "ALTER TABLE datos_equipo ADD COLUMN IF NOT EXISTS entrenador_nombre VARCHAR(150)",
        "ALTER TABLE temporada ADD COLUMN IF NOT EXISTS id_equipo UUID REFERENCES equipo(id_equipo) ON DELETE CASCADE",
        "ALTER TABLE miembro_club ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "ALTER TABLE miembro_club ADD COLUMN IF NOT EXISTS invite_token VARCHAR(64)",
        "ALTER TABLE miembro_club ADD COLUMN IF NOT EXISTS invite_expires TIMESTAMP",
        # Orden crítico: primero quitar el CHECK viejo (admin|editor|lector),
        # luego migrar valores, luego crear el CHECK nuevo (admin|miembro).
        "ALTER TABLE miembro_club DROP CONSTRAINT IF EXISTS ck_miembro_permiso",
        """
        UPDATE miembro_club SET permiso = 'miembro'
        WHERE permiso IS NULL OR permiso = ''
           OR permiso NOT IN ('administrador', 'miembro')
        """,
        """
        DO $$ BEGIN
          ALTER TABLE miembro_club
            ADD CONSTRAINT ck_miembro_permiso
            CHECK (permiso IN ('administrador', 'miembro'));
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """,
        """
        UPDATE miembro_club SET cargo = 'Staff'
        WHERE cargo IN ('Analista', 'Director / Gestor', 'Administrador')
           OR cargo IS NULL OR cargo = ''
        """,
        """
        DO $$ BEGIN
          CREATE UNIQUE INDEX IF NOT EXISTS uq_miembro_invite_token
            ON miembro_club (invite_token)
            WHERE invite_token IS NOT NULL;
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$;
        """,
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS id_equipo UUID REFERENCES equipo(id_equipo) ON DELETE CASCADE",
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS id_rival UUID",
        "ALTER TABLE partido ADD COLUMN IF NOT EXISTS es_local BOOLEAN DEFAULT TRUE",
        "ALTER TABLE partido ALTER COLUMN id_equipo_local DROP NOT NULL",
        "ALTER TABLE partido ALTER COLUMN id_equipo_visitante DROP NOT NULL",
        """
        UPDATE jugador SET img_foto = NULL
        WHERE img_foto IS NOT NULL
          AND (img_foto LIKE 'data:%' OR char_length(img_foto) > 255)
        """,
        """
        UPDATE datos_equipo SET img_escudo = NULL
        WHERE img_escudo IS NOT NULL
          AND (img_escudo LIKE 'data:%' OR char_length(img_escudo) > 255)
        """,
        "ALTER TABLE jugador ALTER COLUMN img_foto TYPE VARCHAR(255)",
        "ALTER TABLE datos_equipo ALTER COLUMN img_escudo TYPE VARCHAR(255)",
        "UPDATE partido SET estado = 'programado' WHERE estado IS NULL",
        "UPDATE temporada SET estado = 'activa' WHERE estado IS NULL",
        """
        UPDATE temporada t SET id_equipo = et.id_equipo
        FROM equipo_temporada et
        WHERE t.id_equipo IS NULL AND et.id_temporada = t.id_temporada
        """,
        """
        UPDATE partido SET id_equipo = id_equipo_local
        WHERE id_equipo IS NULL AND id_equipo_local IS NOT NULL
        """,
        """
        UPDATE partido SET es_local = TRUE
        WHERE es_local IS NULL AND id_equipo IS NOT NULL
          AND id_equipo_local = id_equipo
        """,
        """
        UPDATE partido SET es_local = FALSE
        WHERE es_local IS NULL AND id_equipo IS NOT NULL
          AND id_equipo_visitante = id_equipo
        """,
    ]
    failures = 0
    for stmt in stmts:
        snippet = " ".join(stmt.split())[:120]
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as exc:
            code = _pg_code(exc)
            if code in _SAFE_PG_CODES:
                logger.info("Schema skip (%s): %s", code, snippet)
                continue
            failures += 1
            logger.error("Schema ALTER fallido (%s): %s — %s", code, snippet, exc)
            if settings.strict_schema:
                raise RuntimeError(
                    f"ensure_schema falló ({code}): {snippet}. "
                    "Corrige la BD o pon STRICT_SCHEMA=false solo en emergencia."
                ) from exc

    if failures:
        logger.warning(
            "ensure_schema: %s sentencia(s) fallaron (strict_schema=%s)",
            failures,
            settings.strict_schema,
        )

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE partido DROP CONSTRAINT IF EXISTS ck_partido_equipos_distintos")
        )
        conn.execute(
            text(
                """
                UPDATE temporada t SET estado = 'cerrada',
                  cerrada_en = COALESCE(t.cerrada_en, NOW())
                WHERE t.estado = 'activa'
                  AND t.id_equipo IS NOT NULL
                  AND t.id_temporada <> (
                    SELECT t2.id_temporada FROM temporada t2
                    WHERE t2.id_equipo = t.id_equipo AND t2.estado = 'activa'
                    ORDER BY t2.fecha_inicio DESC NULLS LAST
                    LIMIT 1
                  )
                """
            )
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio

    set_main_loop(asyncio.get_running_loop())
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    with engine.begin() as conn:
        try:
            conn.execute(
                text(
                    """
                    DO $$ BEGIN
                      ALTER TABLE partido
                        ADD CONSTRAINT fk_partido_rival
                        FOREIGN KEY (id_rival) REFERENCES rival(id_rival)
                        ON DELETE RESTRICT;
                    EXCEPTION WHEN duplicate_object THEN NULL;
                    END $$;
                    """
                )
            )
        except Exception as exc:
            logger.error("FK rival: %s", exc)
            if settings.strict_schema:
                raise
    uploads_root()
    db = SessionLocal()
    try:
        seed_catalogos(db)
        from app.routers.estadisticas import rebuild_estadistica_portero

        n = rebuild_estadistica_portero(db)
        if n:
            db.commit()
            logger.info("Reconstruidas %s filas de estadistica_portero desde acciones", n)
        else:
            db.commit()
    finally:
        db.close()
    yield
    set_main_loop(None)


app = FastAPI(title="SIETE Balonmano API", version="2.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(equipos_router, prefix="/api")
app.include_router(rivales_router, prefix="/api")
app.include_router(temporadas_router, prefix="/api")
app.include_router(catalogos_router, prefix="/api")
app.include_router(jugadores_router, prefix="/api")
app.include_router(partidos_router, prefix="/api")
app.include_router(convocatorias_router, prefix="/api")
app.include_router(cuotas_router, prefix="/api")
app.include_router(alineaciones_router, prefix="/api")
app.include_router(jugadas_router, prefix="/api")
app.include_router(preparaciones_router, prefix="/api")
app.include_router(miembros_router, prefix="/api")
app.include_router(estadisticas_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")

# WebSocket: include_router solo-WS puede quedar vacío en FastAPI 0.141+
from app.routers.ws import club_ws as club_ws_endpoint

app.add_api_websocket_route("/api/ws", club_ws_endpoint)

uploads_path = Path(settings.uploads_dir).resolve()
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database_unavailable") from None
    return {"status": "ok", "database": "ok", "build": "lanz-fix-1"}
