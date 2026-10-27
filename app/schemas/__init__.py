"""Esquemas Pydantic de la API, agrupados por dominio.

Se reexporta todo para mantener `from app import schemas` / `schemas.X`.
"""

from app.auth import hash_password as hash_password  # reexport

from app.schemas.common import *  # noqa: F401,F403
from app.schemas.equipo import *  # noqa: F401,F403
from app.schemas.jugadores import *  # noqa: F401,F403
from app.schemas.partidos import *  # noqa: F401,F403
from app.schemas.estadisticas import *  # noqa: F401,F403
from app.schemas.auth import *  # noqa: F401,F403
from app.schemas.dashboard import *  # noqa: F401,F403
from app.schemas.convocatorias import *  # noqa: F401,F403
from app.schemas.miembros import *  # noqa: F401,F403
from app.schemas.jugadas import *  # noqa: F401,F403
from app.schemas.asistencias import *  # noqa: F401,F403
from app.schemas.cuotas import *  # noqa: F401,F403
from app.schemas.preparacion import *  # noqa: F401,F403
from app.schemas.auditoria import *  # noqa: F401,F403
