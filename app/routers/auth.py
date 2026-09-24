from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import (
    create_token,
    get_current_equipo,
    get_current_session,
    hash_password,
    needs_rehash,
    require_admin,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _nombre_desde_correo(correo: str) -> str:
    local = (correo or "usuario").split("@")[0]
    return local.replace(".", " ").replace("_", " ").title() or "Usuario"


def temporada_actual(hoy: date | None = None) -> tuple[str, date, date]:
    """Temporada oct→mar, p.ej. oct 2026 – mar 2027."""
    hoy = hoy or date.today()
    start_year = hoy.year - 1 if hoy.month <= 3 else hoy.year
    nombre = f"{start_year}/{str(start_year + 1)[-2:]}"
    return nombre, date(start_year, 10, 1), date(start_year + 1, 3, 31)


def _equipo_out(db: Session, id_equipo) -> models.Equipo:
    return (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.id_equipo == id_equipo)
        .one()
    )


def _auth_out(
    db: Session,
    equipo: models.Equipo,
    *,
    miembro: models.MiembroClub | None = None,
) -> schemas.AuthOut:
    token = create_token(
        equipo.id_equipo,
        id_miembro=miembro.id_miembro if miembro else None,
        permiso=(
            "administrador"
            if (miembro and miembro.permiso == "administrador") or not miembro
            else "miembro"
        ),
    )
    sesion = None
    if miembro:
        sesion = schemas.MiembroSesionOut(
            id_miembro=miembro.id_miembro,
            nombre=miembro.nombre,
            correo=miembro.correo,
            cargo=miembro.cargo,
            permiso="administrador" if miembro.permiso == "administrador" else "miembro",
        )
    return schemas.AuthOut(token=token, equipo=equipo, miembro=sesion)


@router.post("/login", response_model=schemas.AuthOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    correo = payload.correo.strip().lower()

    # 1) Cuenta del club (dueño)
    equipo = (
        db.query(models.Equipo)
        .options(joinedload(models.Equipo.datos))
        .filter(models.Equipo.correo == correo)
        .first()
    )
    if equipo and verify_password(payload.password, equipo.password_hash):
        if needs_rehash(equipo.password_hash):
            equipo.password_hash = hash_password(payload.password)
            db.commit()
            db.refresh(equipo)
        # La cuenta del club entra como el miembro de ese correo (permiso real, p.ej. tras traspaso)
        from app.routers.miembros import miembro_para_cuenta_club

        miembro_club = miembro_para_cuenta_club(db, equipo)
        return _auth_out(db, equipo, miembro=miembro_club)

    # 2) Miembro invitado con contraseña propia
    miembro = (
        db.query(models.MiembroClub)
        .options(joinedload(models.MiembroClub.equipo).joinedload(models.Equipo.datos))
        .filter(
            models.MiembroClub.correo == correo,
            models.MiembroClub.estado == "activo",
            models.MiembroClub.password_hash.isnot(None),
        )
        .first()
    )
    if not miembro or not verify_password(payload.password, miembro.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    if needs_rehash(miembro.password_hash):
        miembro.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(miembro)
    equipo = miembro.equipo or _equipo_out(db, miembro.id_equipo)
    return _auth_out(db, equipo, miembro=miembro)


@router.get("/invitacion/{token}", response_model=schemas.InvitacionInfoOut)
def invitacion_info(token: str, db: Session = Depends(get_db)):
    miembro = (
        db.query(models.MiembroClub)
        .options(joinedload(models.MiembroClub.equipo).joinedload(models.Equipo.datos))
        .filter(models.MiembroClub.invite_token == token)
        .first()
    )
    if not miembro:
        raise HTTPException(status_code=404, detail="Invitación no válida o ya usada")
    club = "Club"
    if miembro.equipo and miembro.equipo.datos:
        club = miembro.equipo.datos.nombre or club
    ya = bool(miembro.password_hash) and miembro.estado == "activo"
    if (
        not ya
        and miembro.invite_expires
        and miembro.invite_expires < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail="La invitación ha caducado. Pide un nuevo enlace.",
        )
    return schemas.InvitacionInfoOut(
        nombre=miembro.nombre,
        correo=miembro.correo,
        cargo=miembro.cargo,
        permiso=miembro.permiso,
        club=club,
        expira=miembro.invite_expires,
        ya_aceptada=ya,
    )


@router.post("/aceptar-invitacion", response_model=schemas.AuthOut)
def aceptar_invitacion(payload: schemas.AceptarInvitacionIn, db: Session = Depends(get_db)):
    miembro = (
        db.query(models.MiembroClub)
        .options(joinedload(models.MiembroClub.equipo).joinedload(models.Equipo.datos))
        .filter(models.MiembroClub.invite_token == payload.token)
        .first()
    )
    if not miembro:
        raise HTTPException(status_code=404, detail="Invitación no válida o ya usada")
    if miembro.estado == "baja":
        raise HTTPException(status_code=400, detail="Este miembro está dado de baja")
    if miembro.invite_expires and miembro.invite_expires < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="La invitación ha caducado. Pide un nuevo enlace.",
        )

    if payload.nombre:
        miembro.nombre = payload.nombre.strip()
    miembro.password_hash = hash_password(payload.password)
    miembro.estado = "activo"
    miembro.invite_token = None
    miembro.invite_expires = None
    db.commit()
    db.refresh(miembro)
    equipo = miembro.equipo or _equipo_out(db, miembro.id_equipo)
    return _auth_out(db, equipo, miembro=miembro)


@router.post("/registro", response_model=schemas.AuthOut, status_code=status.HTTP_201_CREATED)
def registro(payload: schemas.RegistroIn, db: Session = Depends(get_db)):
    if db.query(models.Equipo).filter(models.Equipo.correo == payload.correo.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Ya existe un equipo con ese correo")

    nombre_temp, inicio_def, fin_def = temporada_actual()
    inicio = payload.temporada_inicio or inicio_def
    fin = payload.temporada_fin or fin_def
    nombre_temporada = payload.temporada_nombre or nombre_temp

    equipo = models.Equipo(
        correo=payload.correo.strip().lower(),
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
    else:
        db.add(
            models.MiembroClub(
                id_equipo=equipo.id_equipo,
                nombre=_nombre_desde_correo(payload.correo),
                correo=payload.correo.strip().lower(),
                cargo="Administrador",
                permiso="administrador",
                estado="activo",
            )
        )
    db.commit()

    equipo = _equipo_out(db, equipo.id_equipo)
    from app.routers.miembros import miembro_para_cuenta_club

    return _auth_out(db, equipo, miembro=miembro_para_cuenta_club(db, equipo))


@router.get("/me", response_model=schemas.EquipoOut)
def me(equipo: models.Equipo = Depends(get_current_equipo)):
    return equipo


@router.get("/sesion", response_model=schemas.SesionOut)
def sesion(session=Depends(get_current_session)):
    miembro = None
    if session.miembro:
        miembro = schemas.MiembroSesionOut(
            id_miembro=session.miembro.id_miembro,
            nombre=session.miembro.nombre,
            correo=session.miembro.correo,
            cargo=session.miembro.cargo,
            permiso=(
                "administrador"
                if session.miembro.permiso == "administrador"
                else "miembro"
            ),
        )
    return schemas.SesionOut(
        equipo=session.equipo,
        miembro=miembro,
        permiso="administrador" if session.is_admin else "miembro",
    )


@router.patch("/me/perfil", response_model=schemas.MiembroSesionOut)
def actualizar_perfil_miembro(
    payload: schemas.MiembroPerfilUpdate,
    session=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not session.miembro:
        raise HTTPException(
            status_code=400,
            detail="Esta acción es para miembros invitados. El dueño edita el club en Ajustes → Club.",
        )
    if payload.nombre:
        session.miembro.nombre = payload.nombre.strip()
        db.commit()
        db.refresh(session.miembro)
    return schemas.MiembroSesionOut(
        id_miembro=session.miembro.id_miembro,
        nombre=session.miembro.nombre,
        correo=session.miembro.correo,
        cargo=session.miembro.cargo,
        permiso=(
            "administrador"
            if session.miembro.permiso == "administrador"
            else "miembro"
        ),
    )


@router.patch("/me/password", response_model=schemas.SesionOut)
def cambiar_password(
    payload: schemas.PasswordChangeIn,
    session=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if session.miembro:
        if not session.miembro.password_hash or not verify_password(
            payload.password_actual, session.miembro.password_hash
        ):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        session.miembro.password_hash = hash_password(payload.password_nueva)
        db.commit()
    else:
        if not verify_password(payload.password_actual, session.equipo.password_hash):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        session.equipo.password_hash = hash_password(payload.password_nueva)
        db.commit()
    return sesion(session)


@router.patch("/me", response_model=schemas.EquipoOut)
def actualizar_cuenta(
    payload: schemas.CuentaUpdate,
    session=Depends(require_admin),
    db: Session = Depends(get_db),
):
    equipo = session.equipo
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
        equipo.datos.nombre_corto = payload.nombre_display.strip() or equipo.datos.nombre_corto

    db.commit()
    return _equipo_out(db, equipo.id_equipo)


@router.patch("/me/datos", response_model=schemas.EquipoOut)
def actualizar_datos(
    payload: schemas.DatosEquipoUpdate,
    session=Depends(require_admin),
    db: Session = Depends(get_db),
):
    equipo = session.equipo
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
    return _equipo_out(db, equipo.id_equipo)
