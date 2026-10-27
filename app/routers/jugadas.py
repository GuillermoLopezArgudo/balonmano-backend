import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_session, AuthSession
from app.database import get_db
from app.permisos import AREA_LABELS

router = APIRouter(prefix="/jugadas", tags=["jugadas"])


def _assert_write(session: AuthSession, ambito: str) -> None:
    area = "fisico" if ambito == "fisico" else "jugadas"
    if not session.can_write_area(area):
        label = AREA_LABELS.get(area, area)
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede modificar {label}",
        )


def _assert_nombre_unico(
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


def _nombre_copia_libre(
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


def _load(db: Session, id_jugada, id_equipo) -> models.Jugada | None:
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


def _out(j: models.Jugada) -> schemas.JugadaOut:
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


def _list_out(j: models.Jugada) -> schemas.JugadaListOut:
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


def _default_contenido(fase: str) -> tuple[list[schemas.JugadaPiezaIn], list[schemas.JugadaPasoIn]]:
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


def _aplicar_contenido(
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


def _assert_read(session: AuthSession, ambito: str) -> None:
    area = "fisico" if ambito == "fisico" else "jugadas"
    if not session.can_read_area(area):
        label = AREA_LABELS.get(area, area)
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede ver {label}",
        )


@router.get("/", response_model=list[schemas.JugadaListOut])
def listar(
    fase: str | None = None,
    ambito: str | None = None,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    ambito_f = ambito if ambito in ("tactica", "fisico") else "tactica"
    _assert_read(session, ambito_f)
    equipo = session.equipo
    q = (
        db.query(models.Jugada)
        .options(joinedload(models.Jugada.pasos), joinedload(models.Jugada.piezas))
        .filter(
            models.Jugada.id_equipo == equipo.id_equipo,
            models.Jugada.ambito == ambito_f,
        )
    )
    if fase in ("ataque", "defensa", "completo"):
        q = q.filter(models.Jugada.fase == fase)
    filas = q.order_by(models.Jugada.actualizado_en.desc()).all()
    return [_list_out(j) for j in filas]


@router.get("/{id_jugada}", response_model=schemas.JugadaOut)
def obtener(
    id_jugada: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    j = _load(db, id_jugada, session.equipo.id_equipo)
    if not j:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")
    _assert_read(session, j.ambito or "tactica")
    return _out(j)


@router.post("/", response_model=schemas.JugadaOut, status_code=201)
def crear(
    payload: schemas.JugadaCreate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    ambito = payload.ambito if payload.ambito in ("tactica", "fisico") else "tactica"
    _assert_write(session, ambito)
    equipo = session.equipo

    fase = payload.fase
    if ambito == "fisico" and fase not in ("ataque", "defensa", "completo"):
        fase = "completo"
    if ambito == "fisico" and not payload.fase:
        fase = "completo"

    nombre = payload.nombre.strip()
    _assert_nombre_unico(db, equipo.id_equipo, nombre, fase, ambito)

    piezas = payload.piezas
    pasos = payload.pasos
    if not piezas or not pasos:
        piezas, pasos = _default_contenido(fase)

    jugada = models.Jugada(
        id_equipo=equipo.id_equipo,
        nombre=nombre,
        fase=fase,
        ambito=ambito,
        descripcion=(payload.descripcion or "").strip() or None,
        fecha_sesion=payload.fecha_sesion,
    )
    db.add(jugada)
    db.flush()
    _aplicar_contenido(db, jugada, piezas, pasos)
    db.commit()
    loaded = _load(db, jugada.id_jugada, equipo.id_equipo)
    if not loaded:
        raise HTTPException(status_code=500, detail="Jugada creada pero no se pudo releer")
    return _out(loaded)


@router.put("/{id_jugada}", response_model=schemas.JugadaOut)
def actualizar(
    id_jugada: str,
    payload: schemas.JugadaUpdate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    equipo = session.equipo
    jugada = _load(db, id_jugada, equipo.id_equipo)
    if not jugada:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")

    ambito = getattr(jugada, "ambito", None) or "tactica"
    if payload.ambito is not None:
        ambito = payload.ambito
    _assert_write(session, ambito)

    if payload.nombre is not None:
        jugada.nombre = payload.nombre.strip()
    if payload.fase is not None:
        jugada.fase = payload.fase
    if payload.ambito is not None:
        jugada.ambito = payload.ambito
    if payload.descripcion is not None:
        jugada.descripcion = payload.descripcion.strip() or None
    if "fecha_sesion" in payload.model_dump(exclude_unset=True):
        jugada.fecha_sesion = payload.fecha_sesion

    if payload.nombre is not None or payload.fase is not None or payload.ambito is not None:
        _assert_nombre_unico(
            db,
            equipo.id_equipo,
            jugada.nombre,
            jugada.fase,
            getattr(jugada, "ambito", None) or "tactica",
            exclude_id=jugada.id_jugada,
        )

    if payload.piezas is not None and payload.pasos is not None:
        _aplicar_contenido(db, jugada, payload.piezas, payload.pasos)
    elif payload.piezas is not None or payload.pasos is not None:
        raise HTTPException(
            status_code=400,
            detail="Al actualizar el contenido envía piezas y pasos juntos",
        )

    db.commit()
    loaded = _load(db, jugada.id_jugada, equipo.id_equipo)
    return _out(loaded)


@router.post("/{id_jugada}/copiar", response_model=schemas.JugadaOut, status_code=201)
def copiar(
    id_jugada: str,
    payload: schemas.JugadaCopiarIn | None = None,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    equipo = session.equipo
    origen = _load(db, id_jugada, equipo.id_equipo)
    if not origen:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")

    ambito = getattr(origen, "ambito", None) or "tactica"
    _assert_write(session, ambito)

    if payload and payload.nombre:
        nombre = payload.nombre.strip()[:120]
        _assert_nombre_unico(db, equipo.id_equipo, nombre, origen.fase, ambito)
    else:
        nombre = _nombre_copia_libre(
            db, equipo.id_equipo, origen.nombre, origen.fase, ambito
        )
    full = _out(origen)

    piezas_in = [
        schemas.JugadaPiezaIn(
            id_pieza=p.id_pieza,
            etiqueta=p.etiqueta,
            color=p.color,
            id_jugador=p.id_jugador,
            orden=p.orden,
        )
        for p in full.piezas
    ]
    pasos_in = [
        schemas.JugadaPasoIn(
            orden=paso.orden,
            titulo=paso.titulo,
            balon_x=paso.balon_x,
            balon_y=paso.balon_y,
            id_pieza_balon=paso.id_pieza_balon,
            posiciones=[
                schemas.JugadaPosicionIn(id_pieza=pos.id_pieza, x=pos.x, y=pos.y)
                for pos in paso.posiciones
            ],
            flechas=[
                schemas.JugadaFlechaIn(
                    id_pieza=f.id_pieza,
                    x1=f.x1,
                    y1=f.y1,
                    x2=f.x2,
                    y2=f.y2,
                    tipo=f.tipo or "movimiento",
                )
                for f in paso.flechas
            ],
        )
        for paso in full.pasos
    ]

    nueva = models.Jugada(
        id_equipo=equipo.id_equipo,
        nombre=nombre[:120],
        fase=origen.fase,
        ambito=ambito,
        descripcion=origen.descripcion,
        fecha_sesion=getattr(origen, "fecha_sesion", None),
    )
    db.add(nueva)
    db.flush()
    _aplicar_contenido(db, nueva, piezas_in, pasos_in)
    db.commit()
    loaded = _load(db, nueva.id_jugada, equipo.id_equipo)
    return _out(loaded)


@router.delete("/{id_jugada}", status_code=204)
def eliminar(
    id_jugada: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    equipo = session.equipo
    jugada = (
        db.query(models.Jugada)
        .filter(
            models.Jugada.id_jugada == id_jugada,
            models.Jugada.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not jugada:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")
    ambito = getattr(jugada, "ambito", None) or "tactica"
    _assert_write(session, ambito)
    db.delete(jugada)
    db.commit()
    return None
