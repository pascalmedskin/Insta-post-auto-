"""Publication Instagram via l'API Graph officielle (compte Business/Creator).

Supporte les tokens par marque (OAuth) et le fallback vers .env global.

Flux :
  POST simple    -> /media (image_url, caption) -> /media_publish
  CAROUSEL       -> N x /media (is_carousel_item) -> /media (CAROUSEL, children)
                    -> /media_publish
  STORY          -> /media (media_type=STORIES, image_url) -> /media_publish

NB : les images doivent être accessibles via une URL PUBLIQUE
(PUBLIC_BASE_URL). En local, utilise un tunnel (ngrok/cloudflared).
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.models import ContentFormat, ContentItem

logger = logging.getLogger(__name__)


class InstagramError(RuntimeError):
    pass


def _base() -> str:
    return f"https://graph.facebook.com/{settings.ig_graph_version}"


def _get_credentials(content: ContentItem) -> tuple:
    brand = content.brand
    if brand and brand.ig_access_token and brand.ig_user_id:
        return brand.ig_access_token, brand.ig_user_id
    if settings.has_instagram:
        return settings.ig_access_token, settings.ig_business_account_id
    raise InstagramError(
        "Instagram non configuré. Connecte ton compte dans l'identité de marque."
    )


def _media_url(rel_path: str) -> str:
    base = settings.public_base_url.rstrip("/")
    rel = rel_path.lstrip("/")
    if not rel.startswith("static/"):
        rel = f"static/{rel}"
    return f"{base}/{rel}"


def _post(path: str, params: dict, access_token: str) -> dict:
    params = {**params, "access_token": access_token}
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{_base()}/{path}", data=params)
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        raise InstagramError(data.get("error", data))
    return data


def _create_container(ig_id: str, params: dict, access_token: str) -> str:
    return _post(f"{ig_id}/media", params, access_token)["id"]


def _publish(ig_id: str, creation_id: str, access_token: str) -> str:
    return _post(f"{ig_id}/media_publish", {"creation_id": creation_id}, access_token)["id"]


def _full_caption(content: ContentItem) -> str:
    parts = [content.caption.strip()]
    if content.hashtags.strip():
        parts.append(content.hashtags.strip())
    return "\n\n".join(p for p in parts if p)


def publish_content(content: ContentItem) -> str:
    """Publie le contenu et renvoie l'ID média Instagram."""
    access_token, ig_id = _get_credentials(content)

    images = content.image_paths or []
    if not images:
        raise InstagramError("Aucun visuel à publier.")

    caption = _full_caption(content)

    if content.format == ContentFormat.STORY:
        cid = _create_container(
            ig_id,
            {"image_url": _media_url(images[0]), "media_type": "STORIES"},
            access_token,
        )
        return _publish(ig_id, cid, access_token)

    if content.format == ContentFormat.CAROUSEL and len(images) > 1:
        children = []
        for path in images[:10]:
            children.append(
                _create_container(
                    ig_id,
                    {"image_url": _media_url(path), "is_carousel_item": "true"},
                    access_token,
                )
            )
        carousel = _create_container(
            ig_id,
            {
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
            },
            access_token,
        )
        return _publish(ig_id, carousel, access_token)

    cid = _create_container(
        ig_id,
        {"image_url": _media_url(images[0]), "caption": caption},
        access_token,
    )
    return _publish(ig_id, cid, access_token)
