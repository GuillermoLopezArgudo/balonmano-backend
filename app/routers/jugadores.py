from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import AuthSession, get_current_equipo, get_current_session, get_equipo_area
from app.database import get_db

router = APIRouter(prefix="/jugadores", tags=["jugadores"])


def _jugador_out(jugador: models.Jugador) -> schemas.JugadorOut:
    activo = next((je for je in jugador.equipos if je.fecha_baja is None), None)
    if activo is None and jugador.equipos:
        activo = jugador.equipos[0]
    equipo_nombre = None
    if activo and activo.equipo and activo.equipo.datos:
        equipo_nombre = activo.equipo.datos.nombre
    pos = next((jp for jp in jugador.posiciones if jp.posicion), None)
    return schemas.JugadorOut(
        id_jugador=jugador.id_jugador,
        nombre=jugador.nombre,
        apellido=jugador.apellido,
        fecha_nacimiento=jugador.fecha_nacimiento,
        altura_cm=jugador.altura_cm,
        peso_kg=jugador.peso_kg,
        img_foto=jugador.img_foto,
        dorsal=activo.dorsal if activo else None,
        id_equipo=activo.id_equipo if activo else None,
        equipo_nombre=equipo_nombre,
        posiciones=[jp.posicion.nombre for jp in jugador.posiciones if jp.posicion],
        id_posicion=pos.id_posicion if pos else None,
        activo=bool(activo and activo.fecha_baja is None),
        disponibilidad=getattr(activo, "disponibilidad", None) or "disponible",
    )


def _load_jugador(db: Session, id_jugador: str) -> models.Jugador | None:
    return (
        db.query(models.Jugador)
        .options(
            joinedload(models.Jugador.equipos).joinedload(models.JugadorEquipo.equipo).joinedload(
                models.Equipo.datos
            ),
            joinedload(models.Jugador.posiciones).joinedload(models.JugadorPosicion.posicion),
        )
        .filter(models.Jugador.id_jugador == id_jugador)
        .first()
    )


def _vinculo_equipo(db: Session, id_jugador: str, id_equipo) -> models.JugadorEquipo | None:
    return (
        db.query(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_jugador == id_jugador,
            models.JugadorEquipo.id_equipo == id_equipo,
        )
        .first()
    )


@router.get("/", response_model=list[schemas.JugadorOut])
def listar(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    jugadores = (
        db.query(models.Jugador)
        .join(models.JugadorEquipo)
        .filter(models.JugadorEquipo.id_equipo == equipo.id_equipo)
        .options(
            joinedload(models.Jugador.equipos).joinedload(models.JugadorEquipo.equipo).joinedload(
                models.Equipo.datos
            ),
            joinedload(models.Jugador.posiciones).joinedload(models.JugadorPosicion.posicion),
        )
        .order_by(models.Jugador.apellido, models.Jugador.nombre)
        .all()
    )
    return [_jugador_out(j) for j in jugadores]


@router.post("/", response_model=schemas.JugadorOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: schemas.JugadorCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("plantilla")),
):
    if payload.id_posicion and not db.get(models.Posicion, payload.id_posicion):
        raise HTTPException(status_code=404, detail="Posición no encontrada")

    jugador = models.Jugador(
        nombre=payload.nombre,
        apellido=payload.apellido,
        fecha_nacimiento=payload.fecha_nacimiento,
        altura_cm=payload.altura_cm,
        peso_kg=payload.peso_kg,
        img_foto=payload.img_foto,
    )
    db.add(jugador)
    db.flush()

    alta = payload.fecha_alta or date.today()
    db.add(
        models.JugadorEquipo(
            id_jugador=jugador.id_jugador,
            id_equipo=equipo.id_equipo,
            dorsal=payload.dorsal,
            fecha_alta=alta,
            fecha_baja=None if payload.activo else alta,
            disponibilidad=payload.disponibilidad or "disponible",
        )
    )
    if payload.id_posicion:
        db.add(
            models.JugadorPosicion(
                id_jugador=jugador.id_jugador,
                id_posicion=payload.id_posicion,
            )
        )

    db.commit()
    return _jugador_out(_load_jugador(db, str(jugador.id_jugador)))


@router.get("/{id_jugador}", response_model=schemas.JugadorOut)
def detalle(
    id_jugador: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    jugador = _load_jugador(db, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if not _vinculo_equipo(db, id_jugador, equipo.id_equipo):
        raise HTTPException(status_code=403, detail="No pertenece a tu equipo")
    return _jugador_out(jugador)


@router.patch("/{id_jugador}", response_model=schemas.JugadorOut)
def actualizar(
    id_jugador: str,
    payload: schemas.JugadorUpdate,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(get_current_session),
):
    puede_plantilla = session.can_write_area("plantilla")
    puede_fisico = session.can_write_area("fisico")
    if not puede_plantilla and not puede_fisico:
        raise HTTPException(
            status_code=403,
            detail=f"Tu cargo ({session.cargo}) no puede modificar plantilla",
        )

    jugador = _load_jugador(db, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    vinculo = _vinculo_equipo(db, id_jugador, session.equipo.id_equipo)
    if not vinculo:
        raise HTTPException(status_code=403, detail="No pertenece a tu equipo")

    data = payload.model_dump(exclude_unset=True)
    if not puede_plantilla:
        if set(data) - {"disponibilidad"} or "disponibilidad" not in data:
            raise HTTPException(
                status_code=403,
                detail="Tu cargo solo puede cambiar la disponibilidad de la jugadora",
            )
    if "id_posicion" in data and data["id_posicion"] is not None:
        if not db.get(models.Posicion, data["id_posicion"]):
            raise HTTPException(status_code=404, detail="Posición no encontrada")

    for key in ("nombre", "apellido", "fecha_nacimiento", "altura_cm", "peso_kg", "img_foto"):
        if key in data:
            setattr(jugador, key, data[key])

    if "dorsal" in data and data["dorsal"] is not None:
        vinculo.dorsal = data["dorsal"]

    if "activo" in data and data["activo"] is not None:
        if data["activo"]:
            vinculo.fecha_baja = None
            if not vinculo.fecha_alta:
                vinculo.fecha_alta = date.today()
        else:
            vinculo.fecha_baja = date.today()

    if "disponibilidad" in data and data["disponibilidad"] is not None:
        vinculo.disponibilidad = data["disponibilidad"]

    if "id_posicion" in data:
        db.query(models.JugadorPosicion).filter(
            models.JugadorPosicion.id_jugador == id_jugador
        ).delete()
        if data["id_posicion"] is not None:
            db.add(
                models.JugadorPosicion(
                    id_jugador=jugador.id_jugador,
                    id_posicion=data["id_posicion"],
                )
            )

    db.commit()
    return _jugador_out(_load_jugador(db, id_jugador))


@router.delete("/{id_jugador}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    id_jugador: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_area("plantilla")),
):
    jugador = db.get(models.Jugador, id_jugador)
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    vinculo = _vinculo_equipo(db, id_jugador, equipo.id_equipo)
    if not vinculo:
        raise HTTPException(status_code=403, detail="No pertenece a tu equipo")
    db.delete(jugador)
    db.commit()
