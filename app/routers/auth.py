from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import create_token, get_current_equipo, hash_password, needs_rehash, verify_password
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def temporada_actual(hoy: date | None = None) -> tuple[str, date, date]:
    """Temporada oct→mar, p.ej. oct 2026 – mar 2027."""
    hoy = hoy or date.today()
    start_year = hoy.year - 1 if hoy.month <= 3 else hoy.year
    nombre = f"{start_year}/{str(start_year + 1)[-2:]}"
    return nombre, date(start_year, 10, 1), date(start_year + 1, 3, 31)


@router.post("/login", response_model=schemas.AuthOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.correo == payload.correo)
        .first()
    )
    if not equipo or not verify_password(payload.password, equipo.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    if needs_rehash(equipo.password_hash):
        equipo.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(equipo)
    return schemas.AuthOut(token=create_token(equipo.id_equipo), equipo=equipo)


@router.post("/registro", response_model=schemas.AuthOut, status_code=status.HTTP_201_CREATED)
def registro(payload: schemas.RegistroIn, db: Session = Depends(get_db)):
    if db.query(models.Equipo).filter(models.Equipo.correo == payload.correo).first():
        raise HTTPException(status_code=400, detail="Ya existe un equipo con ese correo")

    nombre_temp, inicio_def, fin_def = temporada_actual()
    inicio = payload.temporada_inicio or inicio_def
    fin = payload.temporada_fin or fin_def
    nombre_temporada = payload.temporada_nombre or nombre_temp

    equipo = models.Equipo(
        correo=payload.correo,
        password_hash=hash_password(payload.password),
        datos=models.DatosEquipo(
            nombre=payload.nombre,
            entrenador_nombre=(payload.entrenador_nombre or "").strip() or None,
            categoria=payload.categoria,
            competicion=payload.competicion,
            img_escudo=payload.img_escudo,
        ),
    )
    db.add(equipo)
    db.flush()

    temporada = models.Temporada(
        id_equipo=equipo.id_equipo,
        nombre=nombre_temporada,
        fecha_inicio=inicio,
        fecha_fin=fin,
        estado="activa",
    )
    db.add(temporada)
    db.flush()

    db.add(
        models.EquipoTemporada(
            id_equipo=equipo.id_equipo,
            id_temporada=temporada.id_temporada,
            categoria=payload.categoria,
            competicion=payload.competicion,
        )
    )

    coach = (payload.entrenador_nombre or "").strip()
    if coach:
        db.add(
            models.MiembroClub(
                id_equipo=equipo.id_equipo,
                nombre=coach,
                correo=payload.correo.strip().lower(),
                cargo="Entrenador principal",
                permiso="administrador",
                estado="activo",
            )
        )
    db.commit()

    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == equipo.id_equipo)
        .one()
    )
    return schemas.AuthOut(token=create_token(equipo.id_equipo), equipo=equipo)


@router.get("/me", response_model=schemas.EquipoOut)
def me(equipo: models.Equipo = Depends(get_current_equipo)):
    return equipo


@router.patch("/me", response_model=schemas.EquipoOut)
def actualizar_cuenta(
    payload: schemas.CuentaUpdate,
    equipo: models.Equipo = Depends(get_current_equipo),
    db: Session = Depends(get_db),
):
    if payload.correo and payload.correo.lower() != equipo.correo.lower():
        exists = (
            db.query(models.Equipo)
            .filter(
                models.Equipo.correo == payload.correo.lower(),
                models.Equipo.id_equipo != equipo.id_equipo,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Ese correo ya está en uso")
        equipo.correo = payload.correo.strip().lower()

    if payload.password_nueva:
        if not payload.password_actual or not verify_password(
            payload.password_actual, equipo.password_hash
        ):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        equipo.password_hash = hash_password(payload.password_nueva)

    if payload.entrenador_nombre is not None and equipo.datos:
        equipo.datos.entrenador_nombre = payload.entrenador_nombre.strip() or None

    if payload.nombre_display is not None and equipo.datos:
        # Solo nombre corto del club, no el del entrenador
        equipo.datos.nombre_corto = payload.nombre_display.strip() or equipo.datos.nombre_corto

    db.commit()
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == equipo.id_equipo)
        .one()
    )
    return equipo


@router.patch("/me/datos", response_model=schemas.EquipoOut)
def actualizar_datos(
    payload: schemas.DatosEquipoUpdate,
    equipo: models.Equipo = Depends(get_current_equipo),
    db: Session = Depends(get_db),
):
    datos = equipo.datos
    if not datos:
        datos = models.DatosEquipo(
            id_equipo=equipo.id_equipo,
            nombre=payload.nombre or "Mi equipo",
        )
        db.add(datos)
        equipo.datos = datos

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(datos, key, value)

    db.commit()
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == equipo.id_equipo)
        .one()
    )
    return equipo
