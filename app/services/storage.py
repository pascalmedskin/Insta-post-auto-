"""Sauvegarde des fichiers uploadés dans static/media."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import MEDIA_DIR

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".svg"}

_MIME_TO_EXT = {
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}


def save_upload(file: UploadFile, prefix: str = "up") -> str:
    """Enregistre un fichier et renvoie son chemin relatif (media/...)."""
    ext = Path(file.filename or "").suffix.lower() or ".png"
    if file.content_type in _MIME_TO_EXT:
        ext = _MIME_TO_EXT[file.content_type]
    if ext not in ALLOWED:
        ext = ".png"
    data = file.file.read()
    if data[:5] in (b"<?xml", b"<svg ") or b"<svg" in data[:200]:
        ext = ".svg"
    fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
    dest = MEDIA_DIR / fname
    with dest.open("wb") as out:
        out.write(data)
    return f"media/{fname}"
