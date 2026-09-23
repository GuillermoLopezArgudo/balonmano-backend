import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import models
from app.auth import get_current_equipo
from app.config import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_BYTES = 2 * 1024 * 1024
TIPOS = {"jugador": "jugadores", "escudo": "escudos"}


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
    _: models.Equipo = Depends(get_current_equipo),
):
    if tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="tipo debe ser jugador o escudo")

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
    dest_dir = uploads_root() / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    dest.write_bytes(data)

    rel = f"/uploads/{folder}/{name}"
    return UploadOut(url=rel, path=rel)
