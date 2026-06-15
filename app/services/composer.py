"""Composition du visuel final : texte (hook / slides) incrusté sur l'image.

Combine génération IA (si dispo) + image de marque + charte graphique.
"""

from __future__ import annotations

import logging
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import MEDIA_DIR, settings
from app.models import Brand, ContentFormat
from app.services.image_gen import FORMAT_SIZE, generate_image

logger = logging.getLogger(__name__)

# Polices candidates (DejaVu est livré avec Pillow).
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _abs(rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    p = MEDIA_DIR / Path(rel_path).name
    return p if p.exists() else None


def _base_image(brand: Brand, ai_path: str | None, size: tuple[int, int]) -> Image.Image:
    """Choisit le fond : image IA > image de marque > aplat de couleur."""
    src = _abs(ai_path) or _abs(brand.brand_image_path)
    if src:
        img = Image.open(src).convert("RGB")
        # Crop "cover" pour remplir le format sans déformer.
        img = _cover(img, size)
    else:
        img = Image.new("RGB", size, brand.primary_color)
    return img


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    w, h = img.size
    scale = max(tw / w, th / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    left = (img.width - tw) // 2
    top = (img.height - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _scrim(img: Image.Image, height_ratio: float = 0.55) -> None:
    """Dégradé sombre en bas pour la lisibilité du texte (in-place)."""
    w, h = img.size
    band_h = int(h * height_ratio)
    gradient = Image.new("L", (1, band_h), 0)
    for y in range(band_h):
        gradient.putpixel((0, y), int(200 * (y / band_h)))
    alpha = gradient.resize((w, band_h))
    overlay = Image.new("RGB", (w, band_h), (0, 0, 0))
    img.paste(overlay, (0, h - band_h), alpha)


def _draw_text_block(
    img: Image.Image,
    text: str,
    *,
    color: str,
    font_size: int,
    y_ratio: float,
    wrap: int,
    align: str = "left",
) -> None:
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    w, h = img.size
    margin = int(w * 0.07)
    lines = textwrap.wrap(text, width=wrap) or [""]
    line_h = int(font_size * 1.25)
    y = int(h * y_ratio)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        if align == "center":
            x = (w - line_w) // 2
        else:
            x = margin
        # Légère ombre pour le contraste.
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=color)
        y += line_h


def _paste_logo(img: Image.Image, brand: Brand) -> None:
    logo = _abs(brand.logo_path)
    if not logo:
        return
    try:
        mark = Image.open(logo).convert("RGBA")
        target_w = int(img.width * 0.18)
        ratio = target_w / mark.width
        mark = mark.resize((target_w, int(mark.height * ratio)), Image.LANCZOS)
        img.paste(mark, (int(img.width * 0.07), int(img.height * 0.05)), mark)
    except Exception:  # pragma: no cover
        logger.exception("Logo non incrustable.")


def _paste_product(img: Image.Image, product) -> None:
    """Incruste l'image produit en respectant ses proportions réelles
    (width_mm / height_mm). Centré dans la moitié haute du visuel."""
    src = _abs(getattr(product, "image_path", None))
    if not src:
        return
    try:
        prod = Image.open(src).convert("RGBA")
    except Exception:  # pragma: no cover
        logger.exception("Image produit illisible.")
        return

    w_mm = getattr(product, "width_mm", None)
    h_mm = getattr(product, "height_mm", None)

    # Zone d'affichage : ~62% de la largeur, ~42% de la hauteur du visuel.
    box_w = int(img.width * 0.62)
    box_h = int(img.height * 0.42)

    # Ratio cible : dimensions réelles si fournies, sinon ratio de l'image.
    if w_mm and h_mm:
        target_ratio = w_mm / h_mm
    else:
        target_ratio = prod.width / prod.height

    # On inscrit le produit dans la box en respectant target_ratio ("contain").
    if box_w / box_h > target_ratio:
        new_h = box_h
        new_w = int(box_h * target_ratio)
    else:
        new_w = box_w
        new_h = int(box_w / target_ratio)

    prod = prod.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)
    x = (img.width - new_w) // 2
    y = int(img.height * 0.10)
    img.paste(prod, (x, y), prod)


def _save(img: Image.Image) -> str:
    fname = f"compose_{uuid.uuid4().hex}.png"
    img.save(MEDIA_DIR / fname, "PNG")
    return f"media/{fname}"


def compose_slide(
    brand: Brand,
    fmt: ContentFormat,
    headline: str,
    body: str = "",
    *,
    brief: str = "",
    angle: str = "",
    generate_ai_image: bool = True,
    product=None,
) -> str:
    """Génère (option IA) + compose un visuel et renvoie son chemin relatif."""
    size = FORMAT_SIZE[fmt]
    ai_path = generate_image(brand, brief, angle, fmt) if generate_ai_image else None
    img = _base_image(brand, ai_path, size)
    if product is not None:
        _paste_product(img, product)
    _scrim(img)
    _paste_logo(img, brand)

    align = "center" if fmt == ContentFormat.STORY else "left"
    if headline:
        _draw_text_block(
            img,
            headline,
            color=brand.secondary_color,
            font_size=int(size[0] * 0.075),
            y_ratio=0.62,
            wrap=22,
            align=align,
        )
    if body:
        _draw_text_block(
            img,
            body,
            color=brand.accent_color,
            font_size=int(size[0] * 0.04),
            y_ratio=0.82,
            wrap=40,
            align=align,
        )
    return _save(img)


def compose_content(brand: Brand, content, use_ai_image: bool | None = None) -> list[str]:
    """Compose tous les visuels d'un ContentItem. Renvoie la liste des chemins.

    `use_ai_image` force (ou désactive) la génération IA d'images ; par défaut
    on l'active si une clé OpenAI est configurée.
    """
    fmt = content.format
    paths: list[str] = []
    gen_ai = settings.has_image_ai if use_ai_image is None else (
        use_ai_image and settings.has_image_ai
    )
    product = getattr(content, "product", None)

    if fmt == ContentFormat.CAROUSEL and content.slides:
        for slide in content.slides:
            paths.append(
                compose_slide(
                    brand,
                    fmt,
                    slide.get("headline", ""),
                    slide.get("body", ""),
                    brief=content.prompt,
                    angle=content.angle,
                    generate_ai_image=gen_ai,
                    product=product,
                )
            )
    elif fmt == ContentFormat.STORY:
        slide = (content.slides or [{}])[0]
        paths.append(
            compose_slide(
                brand,
                fmt,
                slide.get("headline", content.hook),
                slide.get("body", ""),
                brief=content.prompt,
                angle=content.angle,
                generate_ai_image=gen_ai,
                product=product,
            )
        )
    else:  # POST
        paths.append(
            compose_slide(
                brand,
                fmt,
                content.hook,
                "",
                brief=content.prompt,
                angle=content.angle,
                generate_ai_image=gen_ai,
                product=product,
            )
        )
    return paths
