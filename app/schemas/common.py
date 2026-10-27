"""Utilidades y tipos compartidos entre esquemas."""

import re
from typing import Annotated

from pydantic import AfterValidator, Field


def _password_fuerte(v: str) -> str:
    if (
        len(v) < 8
        or not re.search(r"[a-z]", v)
        or not re.search(r"[A-Z]", v)
        or not re.search(r"\d", v)
    ):
        raise ValueError(
            "La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número."
        )
    return v


PasswordNueva = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(_password_fuerte)]
