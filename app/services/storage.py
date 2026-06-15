"""Sauvegarde des fichiers uploadés dans static/media."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import MEDIA_DIR

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}


def save_upload(file: UploadFile, prefix: str = "up") -> str:
    """Enregistre un fichier et renvoie son chemin relatif (media/...)."""
    ext = Path(file.filename or "").suffix.lower() or ".png"
    if ext not in ALLOWED:
        ext = ".png"
    fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
    dest = MEDIA_DIR / fname
    with dest.open("wb") as out:
        out.write(file.file.read())
    return f"media/{fname}"
