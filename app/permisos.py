"""Permisos por cargo del club. El flag administrador es independiente (gestión del club)."""

from __future__ import annotations

CARGOS = (
    "Entrenador principal",
    "Segundo entrenador",
    "Preparador físico",
    "Delegado",
    "Staff",
)

CARGOS_UNICOS = frozenset({"Entrenador principal", "Segundo entrenador"})

# Áreas de la app → quién puede escribir
# Lectura: casi todos los cargos activos (salvo none en directo/jugadas para staff)
_WRITE = {
    "Entrenador principal": {
        "plantilla",
        "partidos",
        "directo",
        "convocatoria",
        "jugadas",
        "fisico",
        "cuotas",
        "analitica",
        "informes",
    },
    "Segundo entrenador": {
        "plantilla",
        "partidos",
        "directo",
        "convocatoria",
        "jugadas",
        "fisico",
        "analitica",
        "informes",
    },
    "Preparador físico": {
        "plantilla",  # fichas / estado físico
        "fisico",
        "analitica",
        "informes",
    },
    "Delegado": {
        "partidos",
        "convocatoria",
        "cuotas",
        "informes",
    },
    "Staff": set(),
}

_READ = {
    "Entrenador principal": {
        "plantilla",
        "partidos",
        "directo",
        "convocatoria",
        "jugadas",
        "fisico",
        "cuotas",
        "analitica",
        "informes",
        "club",
    },
    "Segundo entrenador": {
        "plantilla",
        "partidos",
        "directo",
        "convocatoria",
        "jugadas",
        "fisico",
        "cuotas",
        "analitica",
        "informes",
        "club",
    },
    "Preparador físico": {
        "plantilla",
        "partidos",
        "convocatoria",
        "jugadas",
        "fisico",
        "analitica",
        "informes",
        "club",
    },
    "Delegado": {
        "plantilla",
        "partidos",
        "convocatoria",
        "fisico",
        "cuotas",
        "analitica",
        "informes",
        "club",
    },
    "Staff": {
        "plantilla",
        "partidos",
        "convocatoria",
        "fisico",
        "analitica",
        "informes",
        "club",
    },
}

AREA_LABELS = {
    "plantilla": "plantilla",
    "partidos": "partidos",
    "directo": "partido en directo",
    "convocatoria": "convocatorias",
    "jugadas": "jugadas",
    "fisico": "preparación física",
    "cuotas": "cuotas",
    "analitica": "analítica",
    "informes": "informes",
    "club": "club",
}


def normalize_cargo(cargo: str | None) -> str:
    c = (cargo or "").strip()
    if c in ("Analista", "Director / Gestor", "Administrador"):
        return "Staff"
    if c in CARGOS:
        return c
    return "Staff"


def can_write_cargo(cargo: str | None, area: str, *, is_admin: bool = False) -> bool:
    if is_admin:
        return True
    return area in _WRITE.get(normalize_cargo(cargo), set())


def can_read_cargo(cargo: str | None, area: str, *, is_admin: bool = False) -> bool:
    if is_admin:
        return True
    c = normalize_cargo(cargo)
    return area in _READ.get(c, set()) or area in _WRITE.get(c, set())


def any_write_cargo(cargo: str | None, *, is_admin: bool = False) -> bool:
    if is_admin:
        return True
    return bool(_WRITE.get(normalize_cargo(cargo)))
