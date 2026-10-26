import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_equipo, get_equipo_write
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_BYTES = 2 * 1024 * 1024
TIPOS = {"jugador": "jugadores", "escudo": "escudos", "partido": "partidos"}


class UploadOut(BaseModel):
    url: str
    path: str


def uploads_root() -> Path:
    root = Path(settings.uploads_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.post("/", response_model=UploadOut)
async def upload_imagen(
    tipo: str = "jugador",
    file: UploadFile = File(...),
    equipo: models.Equipo = Depends(get_equipo_write),
):
    if tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="tipo debe ser jugador, escudo o partido")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Solo PNG, JPG o WEBP")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="La imagen no puede superar 2MB")
    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    folder = TIPOS[tipo]
    ext = ALLOWED[content_type]
    name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = uploads_root() / str(equipo.id_equipo) / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    dest.write_bytes(data)

    rel = f"/uploads/{equipo.id_equipo}/{folder}/{name}"
    return UploadOut(url=rel, path=rel)


def _candidatos(rel: str) -> list[str]:
    base = rel.replace("\\", "/").lstrip("/")
    if base.startswith("uploads/"):
        base = base[len("uploads/") :]
    return list({f"/uploads/{base}", f"uploads/{base}", base, f"/{base}"})


def _es_de_este_club(db: Session, equipo: models.Equipo, rel: str) -> bool:
    """Fotos antiguas, sin carpeta de club: solo si están guardadas en este equipo."""
    vals = _candidatos(rel)
    jugador = (
        db.query(models.Jugador.id_jugador)
        .join(models.JugadorEquipo)
        .filter(
            models.JugadorEquipo.id_equipo == equipo.id_equipo,
            models.Jugador.img_foto.in_(vals),
        )
        .first()
    )
    if jugador:
        return True
    escudo = (
        db.query(models.DatosEquipo.id_equipo)
        .filter(
            models.DatosEquipo.id_equipo == equipo.id_equipo,
            models.DatosEquipo.img_escudo.in_(vals),
        )
        .first()
    )
    if escudo:
        return True
    partido = (
        db.query(models.Partido.id_partido)
        .filter(
            models.Partido.id_equipo == equipo.id_equipo,
            models.Partido.img_portada.in_(vals),
        )
        .first()
    )
    return partido is not None


@router.get("/file")
def leer_archivo(
    path: str,
    equipo: models.Equipo = Depends(get_current_equipo),
    db: Session = Depends(get_db),
):
    """Foto solo con sesión de este club. Otro equipo, aunque tenga el enlace, no la abre."""
    raw = (path or "").replace("\\", "/").strip()
    if raw.startswith(("http://", "https://", "data:", "blob:")) or ".." in raw:
        raise HTTPException(status_code=404, detail="No encontrado")
    marker = "/uploads/"
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    raw = raw.lstrip("/")
    if raw.startswith("uploads/"):
        raw = raw[len("uploads/") :]
    parts = [p for p in raw.split("/") if p and p != "."]
    folders = set(TIPOS.values())
    if len(parts) == 3 and parts[1] in folders:
        if parts[0] != str(equipo.id_equipo):
            raise HTTPException(status_code=404, detail="No encontrado")
    elif len(parts) == 2 and parts[0] in folders:
        if not _es_de_este_club(db, equipo, "/".join(parts)):
            raise HTTPException(status_code=404, detail="No encontrado")
    else:
        raise HTTPException(status_code=404, detail="No encontrado")
    root = uploads_root()
    target = (root.joinpath(*parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="No encontrado") from None
    if not target.is_file():
        raise HTTPException(status_code=404, detail="No encontrado")
    return FileResponse(target)
