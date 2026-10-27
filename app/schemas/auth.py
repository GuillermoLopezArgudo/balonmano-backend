"""Autenticación, sesión e invitaciones."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field
from app.schemas.common import PasswordNueva
from app.schemas.equipo import EquipoOut


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
    password_nueva: PasswordNueva


class ForgotPasswordIn(BaseModel):
    correo: str = Field(min_length=3, max_length=255)


class ForgotPasswordOut(BaseModel):
    ok: bool = True
    message: str
    # Solo en desarrollo / sin SMTP: facilita probar el flujo
    reset_url: str | None = None


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=2000)
    password: PasswordNueva


class MiembroPerfilUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)


class AceptarInvitacionIn(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    password: PasswordNueva
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
    password: PasswordNueva
    nombre: str = Field(min_length=1, max_length=150)
    entrenador_nombre: str | None = Field(default=None, max_length=150)
    categoria: str | None = Field(default=None, max_length=100)
    competicion: str | None = Field(default=None, max_length=100)
    img_escudo: str | None = Field(default=None, max_length=255)
    temporada_nombre: str = Field(default="2025/26", max_length=100)
    temporada_inicio: date | None = None
    temporada_fin: date | None = None
