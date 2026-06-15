"""Génération d'images IA (OpenAI) — optionnelle.

Si aucune clé OpenAI n'est configurée, renvoie None et le composer
utilisera l'image de marque comme fond.
"""

from __future__ import annotations

import base64
import logging
import uuid

from app.config import MEDIA_DIR, settings
from app.models import Brand, ContentFormat

logger = logging.getLogger(__name__)

# Tailles cibles Instagram (largeur x hauteur).
FORMAT_SIZE = {
    ContentFormat.POST: (1080, 1080),
    ContentFormat.CAROUSEL: (1080, 1350),
    ContentFormat.STORY: (1080, 1920),
}

# OpenAI gpt-image-1 ne supporte que certaines tailles -> on mappe au plus proche.
OPENAI_SIZE = {
    ContentFormat.POST: "1024x1024",
    ContentFormat.CAROUSEL: "1024x1536",
    ContentFormat.STORY: "1024x1536",
}


def _image_prompt(brand: Brand, brief: str, angle: str) -> str:
    return (
        f"Visuel Instagram pour la marque '{brand.name}'. "
        f"Sujet : {brief}. Angle : {angle}. "
        f"Style cohérent avec ces couleurs de marque : {brand.primary_color}, "
        f"{brand.secondary_color}, accent {brand.accent_color}. "
        "Composition épurée, espace négatif en haut ou au centre pour pouvoir "
        "incruster du texte, qualité éditoriale, pas de texte dans l'image."
    )


def generate_image(
    brand: Brand, brief: str, angle: str, fmt: ContentFormat
) -> str | None:
    """Génère une image et renvoie son chemin relatif (media/...), ou None."""
    if not settings.has_image_ai:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        result = client.images.generate(
            model=settings.image_model,
            prompt=_image_prompt(brand, brief, angle),
            size=OPENAI_SIZE.get(fmt, "1024x1024"),
            n=1,
        )
        b64 = result.data[0].b64_json
        raw = base64.b64decode(b64)
        fname = f"gen_{uuid.uuid4().hex}.png"
        (MEDIA_DIR / fname).write_bytes(raw)
        return f"media/{fname}"
    except Exception:  # pragma: no cover - dépend du réseau / quota
        logger.exception("Échec génération image IA, fallback image de marque.")
        return None
