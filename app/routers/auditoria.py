from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.audit import RETENTION_DAYS, purge_old
from app.auth import AuthSession, require_admin
from app.database import get_db

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/", response_model=schemas.AuditLogListOut)
def listar_auditoria(
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    accion: str | None = Query(None, max_length=80),
    q: str | None = Query(None, max_length=120),
):
    """Historial de accesos y cambios del club. Solo administradores."""
    try:
        purge_old(db, id_equipo=session.equipo.id_equipo)
        db.commit()
    except Exception:
        db.rollback()

    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    query = db.query(models.AuditLog).filter(
        models.AuditLog.id_equipo == session.equipo.id_equipo,
        models.AuditLog.creado_en >= cutoff,
    )
    if accion:
        query = query.filter(models.AuditLog.accion == accion.strip())
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.AuditLog.resumen.ilike(like),
                models.AuditLog.actor_nombre.ilike(like),
                models.AuditLog.actor_correo.ilike(like),
                models.AuditLog.ip.ilike(like),
                models.AuditLog.accion.ilike(like),
            )
        )

    total = query.count()
    rows = (
        query.order_by(models.AuditLog.creado_en.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return schemas.AuditLogListOut(
        items=[schemas.AuditLogOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        retention_days=RETENTION_DAYS,
    )
