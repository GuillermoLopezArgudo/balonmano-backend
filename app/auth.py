import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app import models
from app.config import settings
from app.database import get_db

security = HTTPBearer(auto_error=False)

# Prefijo para hashes bcrypt; hashes SHA-256 legacy se verifican y rehashean al login.
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith(_BCRYPT_PREFIXES):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
    # Legacy SHA-256 (sin salt) — solo para migrar cuentas existentes
    import hashlib

    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return legacy == password_hash


def needs_rehash(password_hash: str) -> bool:
    return not (password_hash or "").startswith(_BCRYPT_PREFIXES)


def create_token(id_equipo: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(id_equipo),
        "iat": now,
        "exp": now + timedelta(hours=settings.auth_token_hours),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def parse_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión caducada"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc


def get_current_equipo(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> models.Equipo:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    id_equipo = parse_token(credentials.credentials)
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == id_equipo)
        .first()
    )
    if not equipo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Equipo no encontrado"
        )
    return equipo


def partido_del_equipo(db: Session, id_partido, id_equipo) -> models.Partido | None:
    """Partido donde el club es local o visitante (legacy) o dueño vía id_equipo."""
    from sqlalchemy import or_

    return (
        db.query(models.Partido)
        .filter(
            models.Partido.id_partido == id_partido,
            or_(
                models.Partido.id_equipo == id_equipo,
                models.Partido.id_equipo_local == id_equipo,
                models.Partido.id_equipo_visitante == id_equipo,
            ),
        )
        .first()
    )
