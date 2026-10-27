from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_session, AuthSession
from app.database import get_db
from app.services.jugadas_service import (
    aplicar_contenido,
    assert_nombre_unico,
    assert_read,
    assert_write,
    default_contenido,
    jugada_list_out,
    jugada_out,
    load_jugada,
    nombre_copia_libre,
)

router = APIRouter(prefix="/jugadas", tags=["jugadas"])


@router.get("/", response_model=list[schemas.JugadaListOut])
def listar(
    fase: str | None = None,
    ambito: str | None = None,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    ambito_f = ambito if ambito in ("tactica", "fisico") else "tactica"
    assert_read(session, ambito_f)
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
    return [jugada_list_out(j) for j in filas]


@router.get("/{id_jugada}", response_model=schemas.JugadaOut)
def obtener(
    id_jugada: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    j = load_jugada(db, id_jugada, session.equipo.id_equipo)
    if not j:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")
    assert_read(session, j.ambito or "tactica")
    return jugada_out(j)


@router.post("/", response_model=schemas.JugadaOut, status_code=201)
def crear(
    payload: schemas.JugadaCreate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    ambito = payload.ambito if payload.ambito in ("tactica", "fisico") else "tactica"
    assert_write(session, ambito)
    equipo = session.equipo

    fase = payload.fase
    if ambito == "fisico" and fase not in ("ataque", "defensa", "completo"):
        fase = "completo"
    if ambito == "fisico" and not payload.fase:
        fase = "completo"

    nombre = payload.nombre.strip()
    assert_nombre_unico(db, equipo.id_equipo, nombre, fase, ambito)

    piezas = payload.piezas
    pasos = payload.pasos
    if not piezas or not pasos:
        piezas, pasos = default_contenido(fase)

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
    aplicar_contenido(db, jugada, piezas, pasos)
    db.commit()
    loaded = load_jugada(db, jugada.id_jugada, equipo.id_equipo)
    if not loaded:
        raise HTTPException(status_code=500, detail="Jugada creada pero no se pudo releer")
    return jugada_out(loaded)


@router.put("/{id_jugada}", response_model=schemas.JugadaOut)
def actualizar(
    id_jugada: str,
    payload: schemas.JugadaUpdate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    equipo = session.equipo
    jugada = load_jugada(db, id_jugada, equipo.id_equipo)
    if not jugada:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")

    ambito = getattr(jugada, "ambito", None) or "tactica"
    if payload.ambito is not None:
        ambito = payload.ambito
    assert_write(session, ambito)

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
        assert_nombre_unico(
            db,
            equipo.id_equipo,
            jugada.nombre,
            jugada.fase,
            getattr(jugada, "ambito", None) or "tactica",
            exclude_id=jugada.id_jugada,
        )

    if payload.piezas is not None and payload.pasos is not None:
        aplicar_contenido(db, jugada, payload.piezas, payload.pasos)
    elif payload.piezas is not None or payload.pasos is not None:
        raise HTTPException(
            status_code=400,
            detail="Al actualizar el contenido envía piezas y pasos juntos",
        )

    db.commit()
    loaded = load_jugada(db, jugada.id_jugada, equipo.id_equipo)
    return jugada_out(loaded)


@router.post("/{id_jugada}/copiar", response_model=schemas.JugadaOut, status_code=201)
def copiar(
    id_jugada: str,
    payload: schemas.JugadaCopiarIn | None = None,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    equipo = session.equipo
    origen = load_jugada(db, id_jugada, equipo.id_equipo)
    if not origen:
        raise HTTPException(status_code=404, detail="Jugada no encontrada")

    ambito = getattr(origen, "ambito", None) or "tactica"
    assert_write(session, ambito)

    # Copia = mismo contenido con «Nombre (copia)» (o «copia 2» si ya existe)
    if payload and payload.nombre and payload.nombre.strip():
        nombre = payload.nombre.strip()[:120]
        try:
            assert_nombre_unico(db, equipo.id_equipo, nombre, origen.fase, ambito)
        except HTTPException:
            nombre = nombre_copia_libre(
                db, equipo.id_equipo, origen.nombre, origen.fase, ambito
            )
    else:
        nombre = nombre_copia_libre(
            db, equipo.id_equipo, origen.nombre, origen.fase, ambito
        )
    full = jugada_out(origen)

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
    aplicar_contenido(db, nueva, piezas_in, pasos_in)
    db.commit()
    loaded = load_jugada(db, nueva.id_jugada, equipo.id_equipo)
    return jugada_out(loaded)


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
    assert_write(session, ambito)
    db.delete(jugada)
    db.commit()
    return None
