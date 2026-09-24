import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_equipo, get_equipo_admin, require_admin
from app.database import get_db
from app.permisos import CARGOS, CARGOS_UNICOS, normalize_cargo
from app.realtime import publish_club

router = APIRouter(prefix="/miembros", tags=["miembros"])

INVITE_DAYS = 7


def _nombre_desde_correo(correo: str) -> str:
    local = (correo or "usuario").split("@")[0]
    return local.replace(".", " ").replace("_", " ").title() or "Usuario"


def _admins_activos(db: Session, id_equipo):
    return (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_equipo == id_equipo,
            models.MiembroClub.permiso == "administrador",
            models.MiembroClub.estado == "activo",
        )
        .order_by(models.MiembroClub.creado_en.asc())
        .all()
    )


def _assert_cargo_cupo(
    db: Session,
    id_equipo,
    cargo: str,
    *,
    exclude_id=None,
) -> str:
    cargo = normalize_cargo(cargo)
    if cargo not in CARGOS:
        raise HTTPException(status_code=400, detail="Cargo no válido")
    if cargo in CARGOS_UNICOS:
        q = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_equipo == id_equipo,
                models.MiembroClub.cargo == cargo,
                models.MiembroClub.estado.in_(("activo", "pendiente")),
            )
        )
        if exclude_id is not None:
            q = q.filter(models.MiembroClub.id_miembro != exclude_id)
        if q.first():
            raise HTTPException(
                status_code=400,
                detail=f"Ya hay un «{cargo}» en el club. Solo puede haber uno.",
            )
    return cargo


def _ensure_single_admin(db: Session, equipo: models.Equipo) -> models.MiembroClub:
    admins = _admins_activos(db, equipo.id_equipo)
    if len(admins) > 1:
        for extra in admins[1:]:
            extra.permiso = "miembro"
        db.commit()
        admins = [admins[0]]
    if admins:
        return admins[0]

    club_mail = (equipo.correo or "").strip().lower()
    candidato = None
    if club_mail:
        candidato = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_equipo == equipo.id_equipo,
                models.MiembroClub.correo == club_mail,
                models.MiembroClub.estado != "baja",
            )
            .first()
        )
    if not candidato:
        candidato = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_equipo == equipo.id_equipo,
                models.MiembroClub.estado == "activo",
            )
            .order_by(models.MiembroClub.creado_en.asc())
            .first()
        )
    if candidato:
        candidato.permiso = "administrador"
        if candidato.estado == "pendiente":
            candidato.estado = "activo"
        db.commit()
        db.refresh(candidato)
        return candidato

    owner = models.MiembroClub(
        id_equipo=equipo.id_equipo,
        nombre=(
            (equipo.datos.entrenador_nombre if equipo.datos else None)
            or _nombre_desde_correo(equipo.correo)
        ),
        correo=equipo.correo,
        cargo="Entrenador principal",
        permiso="administrador",
        estado="activo",
        password_hash=None,
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def _ensure_owner(db: Session, equipo: models.Equipo) -> models.MiembroClub:
    club_mail = (equipo.correo or "").strip().lower()
    if club_mail:
        exists = (
            db.query(models.MiembroClub)
            .filter(
                models.MiembroClub.id_equipo == equipo.id_equipo,
                models.MiembroClub.correo == club_mail,
            )
            .first()
        )
        if not exists:
            hay_admin = bool(_admins_activos(db, equipo.id_equipo))
            # Cupo de entrenador principal
            hay_ep = (
                db.query(models.MiembroClub)
                .filter(
                    models.MiembroClub.id_equipo == equipo.id_equipo,
                    models.MiembroClub.cargo == "Entrenador principal",
                    models.MiembroClub.estado.in_(("activo", "pendiente")),
                )
                .first()
            )
            cargo = "Entrenador principal" if not hay_ep else "Staff"
            nombre = None
            if equipo.datos and equipo.datos.entrenador_nombre:
                nombre = equipo.datos.entrenador_nombre
            if not nombre:
                nombre = _nombre_desde_correo(equipo.correo)
            db.add(
                models.MiembroClub(
                    id_equipo=equipo.id_equipo,
                    nombre=nombre,
                    correo=club_mail,
                    cargo=cargo,
                    permiso="administrador" if not hay_admin else "miembro",
                    estado="activo",
                    password_hash=None,
                )
            )
            db.commit()
    return _ensure_single_admin(db, equipo)


def _miembro_cuenta_club(db: Session, equipo: models.Equipo) -> models.MiembroClub | None:
    club_mail = (equipo.correo or "").strip().lower()
    if not club_mail:
        return None
    _ensure_owner(db, equipo)
    return (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_equipo == equipo.id_equipo,
            models.MiembroClub.correo == club_mail,
        )
        .first()
    )


def _issue_invite(m: models.MiembroClub) -> str:
    token = secrets.token_urlsafe(32)
    m.invite_token = token
    m.invite_expires = datetime.utcnow() + timedelta(days=INVITE_DAYS)
    m.estado = "pendiente"
    m.password_hash = None
    return token


def _out(
    m: models.MiembroClub,
    *,
    invite_token: str | None = None,
    correo_club: str | None = None,
) -> schemas.MiembroOut:
    invite_url = f"/invitar/{invite_token}" if invite_token else None
    es_cuenta_club = bool(correo_club) and m.correo.lower() == correo_club.lower()
    return schemas.MiembroOut(
        id_miembro=m.id_miembro,
        id_equipo=m.id_equipo,
        nombre=m.nombre,
        correo=m.correo,
        cargo=m.cargo,
        permiso="administrador" if m.permiso == "administrador" else "miembro",
        estado=m.estado,
        tiene_acceso=es_cuenta_club or bool(m.password_hash),
        invite_url=invite_url,
    )


@router.get("/", response_model=list[schemas.MiembroOut])
def list_miembros(
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_current_equipo),
):
    _ensure_owner(db, equipo)
    rows = (
        db.query(models.MiembroClub)
        .filter(models.MiembroClub.id_equipo == equipo.id_equipo)
        .order_by(models.MiembroClub.creado_en.asc())
        .all()
    )
    return [_out(r, correo_club=equipo.correo) for r in rows]


@router.post("/", response_model=schemas.MiembroOut, status_code=201)
def invite_miembro(
    payload: schemas.MiembroCreate,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    _ensure_owner(db, equipo)
    correo = payload.correo.strip().lower()
    if correo == (equipo.correo or "").strip().lower():
        raise HTTPException(
            status_code=400,
            detail="Ese correo es el del club. Usa otro correo para invitar staff.",
        )
    cargo = _assert_cargo_cupo(db, equipo.id_equipo, payload.cargo)
    row = models.MiembroClub(
        id_equipo=equipo.id_equipo,
        nombre=payload.nombre.strip(),
        correo=correo,
        cargo=cargo,
        permiso="miembro",
        estado="pendiente",
    )
    token = _issue_invite(row)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ya existe un miembro con ese correo")
    db.refresh(row)
    publish_club(
        equipo.id_equipo,
        {
            "type": "miembros.changed",
            "action": "created",
            "id_miembro": str(row.id_miembro),
        },
    )
    return _out(row, invite_token=token, correo_club=equipo.correo)


@router.post("/{id_miembro}/reinvitar", response_model=schemas.MiembroOut)
def reinvitar_miembro(
    id_miembro: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    row = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if row.permiso == "administrador":
        raise HTTPException(status_code=400, detail="El administrador no necesita invitación")
    token = _issue_invite(row)
    db.commit()
    db.refresh(row)
    publish_club(
        equipo.id_equipo,
        {
            "type": "miembros.changed",
            "action": "reinvite",
            "id_miembro": str(row.id_miembro),
        },
    )
    return _out(row, invite_token=token, correo_club=equipo.correo)


@router.post("/{id_miembro}/hacer-administrador", response_model=schemas.MiembroOut)
def transferir_administrador(
    id_miembro: str,
    db: Session = Depends(get_db),
    session=Depends(require_admin),
):
    equipo = session.equipo
    _ensure_owner(db, equipo)
    target = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if target.estado == "baja":
        raise HTTPException(
            status_code=400,
            detail="Reactiva al miembro antes de darle la administración",
        )
    if target.permiso == "administrador":
        return _out(target, correo_club=equipo.correo)

    for admin in _admins_activos(db, equipo.id_equipo):
        admin.permiso = "miembro"

    target.permiso = "administrador"
    if target.estado == "pendiente":
        target.estado = "activo"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se pudo traspasar la administración (restricción de base de datos). Reinicia el backend e inténtalo de nuevo.",
        )
    db.refresh(target)
    publish_club(
        equipo.id_equipo,
        {
            "type": "miembros.changed",
            "action": "admin_transfer",
            "id_miembro": str(target.id_miembro),
            "refresh_sesion": True,
        },
    )
    return _out(target, correo_club=equipo.correo)


@router.patch("/{id_miembro}", response_model=schemas.MiembroOut)
def update_miembro(
    id_miembro: str,
    payload: schemas.MiembroUpdate,
    db: Session = Depends(get_db),
    session=Depends(require_admin),
):
    equipo = session.equipo
    row = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    data = payload.model_dump(exclude_unset=True)
    if "permiso" in data:
        raise HTTPException(
            status_code=400,
            detail="El acceso al club se gestiona con «Traspasar administración». Los permisos de páginas dependen del cargo.",
        )

    if "cargo" in data and data["cargo"] is not None:
        data["cargo"] = _assert_cargo_cupo(
            db, equipo.id_equipo, data["cargo"], exclude_id=row.id_miembro
        )

    if data.get("estado") == "baja" and row.permiso == "administrador":
        raise HTTPException(
            status_code=400,
            detail="Traspasa la administración antes de dar de baja al administrador",
        )

    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip()
        setattr(row, k, v)
    if row.estado == "baja":
        row.invite_token = None
        row.invite_expires = None
    db.commit()
    db.refresh(row)
    publish_club(
        equipo.id_equipo,
        {
            "type": "miembros.changed",
            "action": "updated",
            "id_miembro": str(row.id_miembro),
            "refresh_sesion": True,
            "cargo": row.cargo,
            "estado": row.estado,
        },
    )
    return _out(row, correo_club=equipo.correo)


@router.delete("/{id_miembro}", status_code=204)
def delete_miembro(
    id_miembro: str,
    db: Session = Depends(get_db),
    equipo: models.Equipo = Depends(get_equipo_admin),
):
    row = (
        db.query(models.MiembroClub)
        .filter(
            models.MiembroClub.id_miembro == id_miembro,
            models.MiembroClub.id_equipo == equipo.id_equipo,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if row.permiso == "administrador":
        raise HTTPException(
            status_code=400,
            detail="Traspasa la administración antes de eliminar al administrador",
        )
    db.delete(row)
    db.commit()
    publish_club(
        equipo.id_equipo,
        {
            "type": "miembros.changed",
            "action": "deleted",
            "id_miembro": id_miembro,
            "refresh_sesion": True,
        },
    )
    return None


def miembro_para_cuenta_club(db: Session, equipo: models.Equipo) -> models.MiembroClub | None:
    return _miembro_cuenta_club(db, equipo)
