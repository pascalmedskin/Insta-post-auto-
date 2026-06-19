"""Scraping de pages web pour extraire les infos produits et images."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.config import MEDIA_DIR

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,image/webp,image/png,image/jpeg,*/*",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8,de;q=0.7",
}

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_MIN_IMG_SIZE = 5_000

_SIZE_SUFFIX_RE = re.compile(r"-\d+x\d+(?=\.\w+$)")
_RESIZE_PARAMS = {"w", "h", "width", "height", "resize", "fit", "size", "quality"}


def fetch_page(url: str, timeout: float = 15.0) -> tuple[str, str]:
    """Récupère le HTML brut + le texte d'une page web. Retourne (html, text)."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=_HEADERS)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        logger.exception("Échec récupération URL: %s", url)
        return "", ""
    return html, _html_to_text(html)[:20000]


def fetch_page_text(url: str, timeout: float = 15.0) -> str:
    """Récupère le contenu textuel d'une page web."""
    _, text = fetch_page(url, timeout)
    return text


def _html_to_text(html: str) -> str:
    """Extraction basique du texte depuis le HTML."""
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)

    html = re.sub(r"<(h[1-6]|p|div|li|tr|br|section|article)[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)

    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"&lt;", "<", html)
    html = re.sub(r"&gt;", ">", html)
    html = re.sub(r"&#\d+;", " ", html)
    html = re.sub(r"&\w+;", " ", html)

    lines = [line.strip() for line in html.splitlines()]
    lines = [l for l in lines if len(l) > 2]
    return "\n".join(lines)


_WEBFLOW_SIZE_RE = re.compile(r"-p-\d+(?=\.\w+$)")


def _normalize_image_url(url: str) -> str:
    """Normalise une URL d'image pour détecter les doublons de taille.

    Gère WordPress (-300x300) et Webflow (-p-500, -p-800).
    """
    parsed = urlparse(url)
    path = _SIZE_SUFFIX_RE.sub("", parsed.path)
    path = _WEBFLOW_SIZE_RE.sub("", path)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_webflow_lightbox_images(html: str) -> list[str]:
    """Extrait les images produit depuis les JSON Webflow w-lightbox.

    Webflow stocke les images de galerie dans des blocs
    <script type="application/json" class="w-json"> avec un group "product-images".
    """
    urls = []
    for block in re.findall(
        r'<script[^>]*type="application/json"[^>]*class="[^"]*w-json[^"]*"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            import json
            data = json.loads(block)
            items = data.get("items", [])
            group = data.get("group", "")
            for item in items:
                url = item.get("url", "")
                if url and item.get("type") == "image":
                    urls.append((url, group))
        except Exception:
            continue
    return urls


def extract_image_urls(html: str, base_url: str) -> list[str]:
    """Extrait les URLs des images produit depuis le HTML.

    Stratégie :
    1. Cherche d'abord les JSON Webflow (w-lightbox) avec group "product-images"
    2. Sinon, fallback sur les <img> src/srcset classiques
    3. Déduplique par URL normalisée (variantes de taille)
    """
    wf_images = _extract_webflow_lightbox_images(html)
    product_imgs = [url for url, group in wf_images if "product" in group.lower()]

    if product_imgs:
        seen = set()
        deduped = []
        for u in product_imgs:
            norm = _normalize_image_url(u)
            if norm not in seen:
                seen.add(norm)
                deduped.append(u)
        return deduped

    raw_urls: list[str] = []
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        if not src.startswith("data:"):
            raw_urls.append(urljoin(base_url, src))
    for srcset in re.findall(r'srcset=["\']([^"\']+)["\']', html, re.IGNORECASE):
        for part in srcset.split(","):
            src = part.strip().split()[0]
            if src and not src.startswith("data:"):
                raw_urls.append(urljoin(base_url, src))
    for og in re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE):
        raw_urls.append(urljoin(base_url, og))
    for og in re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE):
        raw_urls.append(urljoin(base_url, og))

    best_per_base: dict[str, str] = {}
    for u in raw_urls:
        norm = _normalize_image_url(u)
        existing = best_per_base.get(norm)
        if existing is None:
            best_per_base[norm] = u
        else:
            size_new = re.search(r"-(\d+)x(\d+)\.", u)
            size_old = re.search(r"-(\d+)x(\d+)\.", existing)
            if (int(size_new.group(1)) if size_new else 99999) > (int(size_old.group(1)) if size_old else 99999):
                best_per_base[norm] = u

    seen = set()
    deduped = []
    for u in raw_urls:
        norm = _normalize_image_url(u)
        best = best_per_base.get(norm, u)
        if best not in seen:
            seen.add(best)
            deduped.append(best)
    return deduped


_SKIP_URL_PATTERNS = [
    "icon", "logo", "favicon", "sprite", "arrow", "btn", "button",
    "social", "facebook", "twitter", "instagram", "linkedin",
    "pixel", "tracking", "analytics", "badge", "flag", "payment",
    "placeholder", "blank", "spacer", "1x1",
]


def _is_meaningful_image(url: str) -> bool:
    """Filtre les icônes, logos, pixels et autres images non-produit."""
    low = url.lower()
    return not any(p in low for p in _SKIP_URL_PATTERNS)


def download_image(url: str, timeout: float = 15.0) -> Optional[tuple]:
    """Télécharge une image. Retourne (chemin_relatif, hash_contenu) ou None."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.content
        if len(data) < _MIN_IMG_SIZE:
            return None
        ct = resp.headers.get("content-type", "")
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
        elif "gif" in ct:
            return None
        elif "svg" in ct:
            return None
        else:
            ext = ".jpg"
        content_hash = hashlib.md5(data).hexdigest()
        fname = f"scraped_{uuid.uuid4().hex}{ext}"
        dest = MEDIA_DIR / fname
        dest.write_bytes(data)
        return f"media/{fname}", content_hash
    except Exception:
        logger.warning("Échec téléchargement image: %s", url)
        return None


def scrape_all_product_images(url: str, max_images: int = 15) -> list[str]:
    """Scrape une page produit et télécharge toutes ses images uniques.

    Déduplique par URL normalisée (variantes de taille WordPress)
    ET par hash de contenu (même image servie depuis des URLs différentes).
    """
    html, _ = fetch_page(url)
    if not html:
        return []

    all_imgs = extract_image_urls(html, url)
    meaningful = [u for u in all_imgs if _is_meaningful_image(u)]
    if not meaningful:
        return []

    logger.info("Page %s : %d images trouvées, %d après filtrage URL", url, len(all_imgs), len(meaningful))

    downloaded = []
    seen_hashes = set()
    for img_url in meaningful[:max_images * 2]:
        result = download_image(img_url)
        if not result:
            continue
        path, content_hash = result
        if content_hash in seen_hashes:
            (MEDIA_DIR / Path(path).name).unlink(missing_ok=True)
            logger.debug("Image dupliquée (contenu identique), ignorée: %s", img_url)
            continue
        seen_hashes.add(content_hash)
        downloaded.append(path)
        if len(downloaded) >= max_images:
            break

    logger.info("Téléchargé %d images uniques depuis %s", len(downloaded), url)
    return downloaded
