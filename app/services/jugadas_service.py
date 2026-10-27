"""Servicios de dominio para jugadas (tácticas y entrenamientos físicos).

Contiene las comprobaciones de permisos, la validación de nombres únicos,
la carga con relaciones, la serialización a esquemas de salida y la
aplicación del contenido (piezas, pasos, posiciones y flechas) de una jugada.
El router ``app.routers.jugadas`` solo orquesta peticiones HTTP y delega aquí.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import AuthSession
from app.permisos import AREA_LABELS


def assert_write(session: AuthSession, ambito: str) -> None:
    area = "fisico" if ambito == "fisico" else "jugadas"
    if not session.can_write_area(area):
        label = AREA_LABELS.get(area, area)
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede modificar {label}",
        )


def assert_nombre_unico(
    db: Session,
    id_equipo,
    nombre: str,
    fase: str,
    ambito: str,
    exclude_id=None,
) -> None:
    """Mismo nombre permitido entre ataque y defensa; no dentro del mismo estilo."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre obligatorio")
    q = db.query(models.Jugada).filter(
        models.Jugada.id_equipo == id_equipo,
        models.Jugada.ambito == ambito,
        models.Jugada.fase == fase,
        models.Jugada.nombre.ilike(nombre),
    )
    if exclude_id is not None:
        q = q.filter(models.Jugada.id_jugada != exclude_id)
    if q.first():
        estilo = {
            "ataque": "ataque",
            "defensa": "defensa",
            "completo": "campo completo",
        }.get(fase, fase)
        tipo = "entrenamiento" if ambito == "fisico" else "jugada"
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una {tipo} de {estilo} con el nombre «{nombre}»",
        )


def nombre_copia_libre(
    db: Session,
    id_equipo,
    base: str,
    fase: str,
    ambito: str,
) -> str:
    base = (base or "Jugada").strip()[:100] or "Jugada"
    for i in range(1, 50):
        candidate = f"{base} (copia)" if i == 1 else f"{base} (copia {i})"
        candidate = candidate[:120]
        exists = (
            db.query(models.Jugada)
            .filter(
                models.Jugada.id_equipo == id_equipo,
                models.Jugada.ambito == ambito,
                models.Jugada.fase == fase,
                models.Jugada.nombre.ilike(candidate),
            )
            .first()
        )
        if not exists:
            return candidate
    return f"{base} ({uuid.uuid4().hex[:6]})"[:120]


def load_jugada(db: Session, id_jugada, id_equipo) -> models.Jugada | None:
    return (
        db.query(models.Jugada)
        .options(
            joinedload(models.Jugada.piezas),
            joinedload(models.Jugada.pasos).joinedload(models.JugadaPaso.posiciones),
            joinedload(models.Jugada.pasos).joinedload(models.JugadaPaso.flechas),
        )
        .filter(
            models.Jugada.id_jugada == id_jugada,
            models.Jugada.id_equipo == id_equipo,
        )
        .first()
    )


def jugada_out(j: models.Jugada) -> schemas.JugadaOut:
    pasos_sorted = sorted(j.pasos or [], key=lambda p: p.orden)
    piezas_sorted = sorted(j.piezas or [], key=lambda p: p.orden)
    return schemas.JugadaOut(
        id_jugada=j.id_jugada,
        nombre=j.nombre,
        fase=j.fase,
        ambito=getattr(j, "ambito", None) or "tactica",
        descripcion=j.descripcion,
        fecha_sesion=getattr(j, "fecha_sesion", None),
        creado_en=j.creado_en,
        actualizado_en=j.actualizado_en,
        piezas=[
            schemas.JugadaPiezaOut(
                id_pieza=p.id_pieza,
                etiqueta=p.etiqueta,
                color=p.color,
                id_jugador=p.id_jugador,
                orden=p.orden,
            )
            for p in piezas_sorted
        ],
        pasos=[
            schemas.JugadaPasoOut(
                id_paso=paso.id_paso,
                orden=paso.orden,
                titulo=paso.titulo,
                balon_x=paso.balon_x,
                balon_y=paso.balon_y,
                id_pieza_balon=paso.id_pieza_balon,
                posiciones=[
                    schemas.JugadaPosicionOut(
                        id_pieza=pos.id_pieza,
                        x=pos.x,
                        y=pos.y,
                    )
                    for pos in (paso.posiciones or [])
                ],
                flechas=[
                    schemas.JugadaFlechaOut(
                        id_flecha=f.id_flecha,
                        id_pieza=f.id_pieza,
                        x1=f.x1,
                        y1=f.y1,
                        x2=f.x2,
                        y2=f.y2,
                        tipo=getattr(f, "tipo", None) or "movimiento",
                    )
                    for f in (paso.flechas or [])
                ],
            )
            for paso in pasos_sorted
        ],
    )


def jugada_list_out(j: models.Jugada) -> schemas.JugadaListOut:
    return schemas.JugadaListOut(
        id_jugada=j.id_jugada,
        nombre=j.nombre,
        fase=j.fase,
        ambito=getattr(j, "ambito", None) or "tactica",
        descripcion=j.descripcion,
        fecha_sesion=getattr(j, "fecha_sesion", None),
        num_pasos=len(j.pasos or []),
        num_piezas=len(j.piezas or []),
        creado_en=j.creado_en,
        actualizado_en=j.actualizado_en,
    )


def default_contenido(fase: str) -> tuple[list[schemas.JugadaPiezaIn], list[schemas.JugadaPasoIn]]:
    """Formación inicial razonable si crean vacía."""
    if fase == "completo":
        # Campo completo: A-* atacan derecha; D-* defienden (6-0).
        layout = [
            ("A-PO", "#ef4444", 4, 50),
            ("A-CE", "#ef4444", 22, 50),
            ("A-LI", "#ef4444", 28, 28),
            ("A-LD", "#ef4444", 28, 72),
            ("A-EI", "#ef4444", 40, 12),
            ("A-ED", "#ef4444", 40, 88),
            ("A-PI", "#ef4444", 46, 50),
            ("D-PO", "#3b82f6", 96, 50),
            ("D-ED", "#3b82f6", 82, 12),
            ("D-LD", "#3b82f6", 78, 28),
            ("D-CE", "#3b82f6", 74, 42),
            ("D-PI", "#3b82f6", 74, 58),
            ("D-LI", "#3b82f6", 78, 72),
            ("D-EI", "#3b82f6", 82, 88),
        ]
    elif fase == "defensa":
        layout = [
            ("EI", "#93c5fd", 8, 78),
            ("LI", "#93c5fd", 20, 55),
            ("CE", "#bfdbfe", 38, 42),
            ("PI", "#bfdbfe", 62, 42),
            ("LD", "#93c5fd", 80, 55),
            ("ED", "#93c5fd", 92, 78),
            ("PO", "#fbbf24", 50, 92),
        ]
    else:
        layout = [
            ("CE", "#a3e635", 50, 12),
            ("LD", "#a3e635", 28, 32),
            ("LI", "#a3e635", 72, 32),
            ("PI", "#d9f99d", 50, 40),
            ("ED", "#a3e635", 14, 82),
            ("EI", "#a3e635", 86, 82),
        ]
    piezas = []
    posiciones = []
    for i, (eti, color, x, y) in enumerate(layout):
        pid = uuid.uuid4()
        piezas.append(
            schemas.JugadaPiezaIn(id_pieza=pid, etiqueta=eti, color=color, orden=i)
        )
        posiciones.append(schemas.JugadaPosicionIn(id_pieza=pid, x=x, y=y))
    first = posiciones[0]
    paso = schemas.JugadaPasoIn(
        id_paso=uuid.uuid4(),
        orden=0,
        titulo="Inicio",
        posiciones=posiciones,
        balon_x=first.x,
        balon_y=first.y,
        id_pieza_balon=first.id_pieza,
    )
    return piezas, [paso]


def aplicar_contenido(
    db: Session,
    jugada: models.Jugada,
    piezas_in: list[schemas.JugadaPiezaIn],
    pasos_in: list[schemas.JugadaPasoIn],
) -> None:
    if len(pasos_in) > 200:
        raise HTTPException(status_code=400, detail="Máximo 200 pasos")
    if len(piezas_in) > 20:
        raise HTTPException(status_code=400, detail="Máximo 20 piezas")

    # Borrar hijos (cascade delete-orphan al clear)
    jugada.pasos.clear()
    jugada.piezas.clear()
    db.flush()

    id_map: dict[uuid.UUID, uuid.UUID] = {}
    for i, p in enumerate(piezas_in):
        new_id = uuid.uuid4()
        if p.id_pieza:
            id_map[p.id_pieza] = new_id
        color = (p.color or None) and str(p.color)[:20]
        pieza = models.JugadaPieza(
            id_pieza=new_id,
            id_jugada=jugada.id_jugada,
            etiqueta=p.etiqueta.strip()[:40] or f"P{i+1}",
            color=color,
            id_jugador=p.id_jugador,
            orden=p.orden if p.orden is not None else i,
        )
        db.add(pieza)
        jugada.piezas.append(pieza)

    # Las piezas deben existir en BD antes de referenciarlas (id_pieza_balon / posiciones)
    db.flush()
    pieza_ids = {pz.id_pieza for pz in jugada.piezas}

    for paso_in in sorted(pasos_in, key=lambda x: x.orden):
        # Solo IDs remapeados: el UUID del cliente no existe en jugada_pieza
        balon_pieza = None
        if paso_in.id_pieza_balon:
            balon_pieza = id_map.get(paso_in.id_pieza_balon)
            if balon_pieza is not None and balon_pieza not in pieza_ids:
                balon_pieza = None
        paso = models.JugadaPaso(
            id_paso=uuid.uuid4(),
            id_jugada=jugada.id_jugada,
            orden=paso_in.orden,
            titulo=(paso_in.titulo or "").strip() or None,
            balon_x=paso_in.balon_x,
            balon_y=paso_in.balon_y,
            id_pieza_balon=balon_pieza,
        )
        db.add(paso)
        db.flush()
        for pos in paso_in.posiciones:
            pid = id_map.get(pos.id_pieza)
            if pid is None or pid not in pieza_ids:
                continue
            db.add(
                models.JugadaPosicion(
                    id_paso=paso.id_paso,
                    id_pieza=pid,
                    x=max(0, min(100, pos.x)),
                    y=max(0, min(100, pos.y)),
                )
            )
        for fle in paso_in.flechas:
            pid = id_map.get(fle.id_pieza)
            if pid is None or pid not in pieza_ids:
                continue
            tipo = fle.tipo if fle.tipo in ("movimiento", "pase", "lanzamiento") else "movimiento"
            db.add(
                models.JugadaFlecha(
                    id_paso=paso.id_paso,
                    id_pieza=pid,
                    x1=max(0, min(100, fle.x1)),
                    y1=max(0, min(100, fle.y1)),
                    x2=max(0, min(100, fle.x2)),
                    y2=max(0, min(100, fle.y2)),
                    tipo=tipo,
                )
            )
        jugada.pasos.append(paso)


def assert_read(session: AuthSession, ambito: str) -> None:
    area = "fisico" if ambito == "fisico" else "jugadas"
    if not session.can_read_area(area):
        label = AREA_LABELS.get(area, area)
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede ver {label}",
        )
