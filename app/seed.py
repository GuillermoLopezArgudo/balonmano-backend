from sqlalchemy.orm import Session

from app import models

POSICIONES = [
    "Portero",
    "Central",
    "Lateral izquierdo",
    "Lateral derecho",
    "Extremo izquierdo",
    "Extremo derecho",
    "Pivote",
]

TIPOS_ACCION = [
    "Gol",
    "Lanzamiento fallado",
    "Parada",
    "Gol recibido",
    "Asistencia",
    "Pérdida",
    "Recuperación",
    "Falta cometida",
    "Falta recibida",
    "Amarilla",
    "Exclusión 2 min",
    "Roja",
    "Azul",
    "Fuera",
    "Poste",
    "Técnica",
]


def seed_catalogos(db: Session) -> None:
    existentes_pos = {p.nombre for p in db.query(models.Posicion).all()}
    for nombre in POSICIONES:
        if nombre not in existentes_pos:
            db.add(models.Posicion(nombre=nombre))

    existentes_acc = {t.nombre for t in db.query(models.TipoAccion).all()}
    for nombre in TIPOS_ACCION:
        if nombre not in existentes_acc:
            db.add(models.TipoAccion(nombre=nombre))

    db.commit()
