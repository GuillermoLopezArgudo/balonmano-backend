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
from app.permisos import AREA_LABELS, any_write_cargo, can_read_cargo, can_write_cargo

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


def create_token(
    id_equipo: uuid.UUID,
    *,
    id_miembro: uuid.UUID | None = None,
    permiso: str | None = None,
    sesion_version: int = 0,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(id_equipo),
        "iat": now,
        "exp": now + timedelta(hours=settings.auth_token_hours),
        "sv": int(sesion_version or 0),
    }
    if id_miembro is not None:
        payload["mid"] = str(id_miembro)
    if permiso:
        payload["perm"] = permiso
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def create_password_reset_token(*, correo: str, kind: str, subject_id: uuid.UUID) -> str:
    """kind: 'equipo' | 'miembro'. Token de un solo uso lógico (caduca en 2 h)."""
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "pwd_reset",
        "kind": kind,
        "email": correo.strip().lower(),
        "sid": str(subject_id),
        "iat": now,
        "exp": now + timedelta(hours=2),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def parse_password_reset_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace ha caducado"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Enlace inválido"
        ) from exc
    if payload.get("purpose") != "pwd_reset":
        raise HTTPException(status_code=400, detail="Enlace inválido")
    kind = payload.get("kind")
    email = (payload.get("email") or "").strip().lower()
    sid = payload.get("sid")
    if kind not in ("equipo", "miembro") or not email or not sid:
        raise HTTPException(status_code=400, detail="Enlace inválido")
    try:
        subject_id = uuid.UUID(str(sid))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Enlace inválido") from exc
    return {"kind": kind, "email": email, "subject_id": subject_id}


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


def parse_token_full(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        try:
            sv = int(payload.get("sv") or 0)
        except (TypeError, ValueError):
            sv = 0
        return {
            "id_equipo": uuid.UUID(payload["sub"]),
            "id_miembro": uuid.UUID(payload["mid"]) if payload.get("mid") else None,
            "permiso": payload.get("perm"),
            "sv": sv,
        }
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
    return get_current_session(credentials, db).equipo


class AuthSession:
    def __init__(
        self,
        equipo: models.Equipo,
        miembro: models.MiembroClub | None = None,
        permiso: str = "administrador",
    ):
        self.equipo = equipo
        self.miembro = miembro
        self.permiso = permiso if permiso == "administrador" else "miembro"

    @property
    def is_admin(self) -> bool:
        return self.permiso == "administrador"

    @property
    def cargo(self) -> str:
        if self.miembro and self.miembro.cargo:
            return self.miembro.cargo
        return "Entrenador principal" if self.is_admin else "Staff"

    @property
    def can_write(self) -> bool:
        return any_write_cargo(self.cargo, is_admin=self.is_admin)

    def can_write_area(self, area: str) -> bool:
        return can_write_cargo(self.cargo, area, is_admin=self.is_admin)

    def can_read_area(self, area: str) -> bool:
        return can_read_cargo(self.cargo, area, is_admin=self.is_admin)


def sesion_vigente(data: dict, equipo: models.Equipo, miembro: models.MiembroClub | None) -> bool:
    """El pase deja de valer cuando cambia la contraseña (sube sesion_version)."""
    claimed = int(data.get("sv") or 0)
    if data.get("id_miembro"):
        actual = int(getattr(miembro, "sesion_version", 0) or 0) if miembro else -1
    else:
        actual = int(getattr(equipo, "sesion_version", 0) or 0)
    return claimed == actual


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    data = parse_token_full(credentials.credentials)
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == data["id_equipo"])
        .first()
    )
    if not equipo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Equipo no encontrado"
        )
    miembro = None
    permiso = "miembro"
    if data.get("id_miembro"):
        miembro = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_miembro == data["id_miembro"],
                models.MiembroClub.id_equipo == equipo.id_equipo,
            )
            .first()
        )
        if not miembro or miembro.estado != "activo":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Miembro no activo o no encontrado",
            )
        permiso = miembro.permiso if miembro.permiso == "administrador" else "miembro"
    else:
        club_mail = (equipo.correo or "").strip().lower()
        if club_mail:
            miembro = (
                db.query(models.MiembroClub)
                .filter(
                    models.MiembroClub.id_equipo == equipo.id_equipo,
                    models.MiembroClub.correo == club_mail,
                    models.MiembroClub.estado == "activo",
                )
                .first()
            )
            if miembro:
                permiso = (
                    miembro.permiso if miembro.permiso == "administrador" else "miembro"
                )
            else:
                permiso = "administrador"
        else:
            permiso = "administrador"
    if not sesion_vigente(data, equipo, miembro if data.get("id_miembro") else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada. Vuelve a entrar.",
        )
    return AuthSession(equipo=equipo, miembro=miembro, permiso=permiso)


def require_write(session: AuthSession = Depends(get_current_session)) -> AuthSession:
    if not session.can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cargo no permite modificar datos",
        )
    return session


def require_admin(session: AuthSession = Depends(get_current_session)) -> AuthSession:
    if not session.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador del club puede hacer esta acción",
        )
    return session


def require_area(area: str):
    """Dependencia: escritura en un área concreta según cargo (admin siempre OK)."""

    def _dep(session: AuthSession = Depends(get_current_session)) -> AuthSession:
        if not session.can_write_area(area):
            label = AREA_LABELS.get(area, area)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu cargo ({session.cargo}) no puede modificar {label}",
            )
        return session

    return _dep


def require_area_read(area: str):
    """Dependencia: lectura en un área concreta según cargo (admin siempre OK)."""

    def _dep(session: AuthSession = Depends(get_current_session)) -> AuthSession:
        if not session.can_read_area(area):
            label = AREA_LABELS.get(area, area)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu cargo ({session.cargo}) no puede ver {label}",
            )
        return session

    return _dep


def get_equipo_write(session: AuthSession = Depends(require_write)) -> models.Equipo:
    return session.equipo


def get_equipo_admin(session: AuthSession = Depends(require_admin)) -> models.Equipo:
    return session.equipo


def get_equipo_area(area: str):
    def _dep(session: AuthSession = Depends(require_area(area))) -> models.Equipo:
        return session.equipo

    return _dep


def get_equipo_area_read(area: str):
    def _dep(session: AuthSession = Depends(require_area_read(area))) -> models.Equipo:
        return session.equipo

    return _dep


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
