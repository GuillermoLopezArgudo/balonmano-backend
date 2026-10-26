from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_AUTH_SECRET = "balonmano-dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/balonmano"
    cors_origins: str = "http://localhost:5173"
    # Obligatorio vía .env — el default solo detecta configuración insegura
    auth_secret: str = _DEV_AUTH_SECRET
    auth_token_hours: int = 72
    uploads_dir: str = "uploads"
    # development | production
    app_env: str = "development"
    # Solo local: permite arrancar con AUTH_SECRET de desarrollo
    allow_insecure_auth: bool = False
    # True = un ALTER fallido en ensure_schema aborta el arranque.
    # En production se fuerza a True salvo que pongas STRICT_SCHEMA=false.
    strict_schema: bool | None = None
    # URL pública del frontend (enlaces de reset de contraseña)
    frontend_url: str = "http://localhost:5173"
    # SMTP opcional (si falta, el reset solo registra el enlace en logs / respuesta en dev)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool = True


settings = Settings()

_is_prod = settings.app_env.lower() in ("production", "prod")

if settings.strict_schema is None:
    object.__setattr__(settings, "strict_schema", _is_prod)

if settings.auth_secret == _DEV_AUTH_SECRET:
    if _is_prod or not settings.allow_insecure_auth:
        raise RuntimeError(
            "AUTH_SECRET no configurado (sigue el valor de desarrollo). "
            "Define AUTH_SECRET en backend/.env con un secreto largo y aleatorio. "
            "Solo en local puedes poner ALLOW_INSECURE_AUTH=true (nunca en producción)."
        )
    import warnings

    warnings.warn(
        "AUTH_SECRET usa el valor por defecto (ALLOW_INSECURE_AUTH=true). "
        "No uses esto fuera de desarrollo local.",
        UserWarning,
        stacklevel=1,
    )

if _is_prod and len(settings.auth_secret) < 32:
    raise RuntimeError("En producción AUTH_SECRET debe tener al menos 32 caracteres.")
