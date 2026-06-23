"""Composition du visuel final — style agence haut de gamme.

Stratégie : photo produit en plein écran + overlay sombre gradient
+ typographie Work Sans + logos de marque SVG.
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

import os as _os
for _d in ["/opt/homebrew/lib", "/usr/local/lib"]:
    if Path(_d).joinpath("libcairo.2.dylib").exists() or Path(_d).joinpath("libcairo.so.2").exists():
        _cur = _os.environ.get("DYLD_LIBRARY_PATH", "")
        if _d not in _cur:
            _os.environ["DYLD_LIBRARY_PATH"] = f"{_d}:{_cur}" if _cur else _d
        break

from app.config import MEDIA_DIR, settings
from app.models import Brand, ContentFormat
from app.services.image_gen import FORMAT_SIZE, generate_full_visual

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"

_font_cache: dict = {}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key in _font_cache:
        return _font_cache[key]
    names = {
        "light": "WorkSans-Light.ttf",
        "regular": "WorkSans-Regular.ttf",
        "medium": "WorkSans-Medium.ttf",
        "semibold": "WorkSans-SemiBold.ttf",
        "bold": "WorkSans-Bold.ttf",
    }
    path = FONTS_DIR / names.get(weight, "WorkSans-Regular.ttf")
    if not path.exists():
        for fb in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            if Path(fb).exists():
                path = Path(fb)
                break
    try:
        f = ImageFont.truetype(str(path), size)
    except OSError:
        f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def _abs(rel_path: Optional[str]) -> Optional[Path]:
    if not rel_path:
        return None
    p = MEDIA_DIR / Path(rel_path).name
    return p if p.exists() else None


def _save(img: Image.Image) -> str:
    fname = f"compose_{uuid.uuid4().hex}.png"
    img.save(MEDIA_DIR / fname, "PNG", quality=95)
    return f"media/{fname}"


def _cover(img: Image.Image, size: tuple) -> Image.Image:
    tw, th = size
    w, h = img.size
    scale = max(tw / w, th / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    left = (img.width - tw) // 2
    top = (img.height - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _open_image(path: Path) -> Optional[Image.Image]:
    if path.suffix.lower() == ".svg":
        try:
            import cairosvg
            with open(path, "rb") as f:
                svg_data = f.read()
            png_data = cairosvg.svg2png(bytestring=svg_data, output_width=1024)
            return Image.open(BytesIO(png_data)).convert("RGBA")
        except Exception as e:
            logger.warning("Cannot open SVG %s: %s", path.name, e)
            return None
    try:
        return Image.open(path)
    except Exception:
        return None


def _get_logo(brand: Brand, variant_keyword: str) -> Optional[Path]:
    logos = brand.logos or []
    for l in logos:
        if isinstance(l, dict):
            v = (l.get("variant", "") or "").lower()
            if variant_keyword in v:
                return _abs(l.get("path"))
    if variant_keyword == "light":
        return _abs(brand.logo_path)
    return None


def _get_product_images(product) -> list:
    if not product:
        return []
    paths = []
    main = getattr(product, "image_path", None)
    if main:
        p = _abs(main)
        if p:
            paths.append(p)
    for item in (getattr(product, "images", None) or []):
        raw = item["path"] if isinstance(item, dict) else item
        p = _abs(raw)
        if p and p not in paths:
            paths.append(p)
    return paths


def _pick_photo(product, index: int = 0) -> Optional[Path]:
    images = _get_product_images(product)
    if not images:
        return None
    return images[index % len(images)]


# ── Drawing helpers ───────────────────────────────────────────────────

def _wrap_text(draw, text: str, font, max_width: int) -> list:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_centered(draw, text, font, y, w, fill=(255, 255, 255, 255)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (w - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _draw_multiline_centered(draw, text, font, y, w, max_width, fill=(255, 255, 255, 255), line_spacing=1.2):
    lines = _wrap_text(draw, text, font, max_width)
    line_h = int(font.size * line_spacing)
    for line in lines:
        _draw_centered(draw, line, font, y, w, fill=fill)
        y += line_h
    return y


def _overlay_gradient(base: Image.Image, opacity: int = 180) -> Image.Image:
    """Full-image gradient: dark top (logo) → lighter middle (product) → dark bottom (text)."""
    w, h = base.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y_pos in range(h):
        ratio = y_pos / h
        if ratio < 0.15:
            # Top: dark for brand name / logo
            progress = 1.0 - (ratio / 0.15)
            a = int(opacity * (0.45 + 0.25 * progress))
        elif ratio < 0.40:
            # Upper-mid: ease out to lighter zone
            progress = (ratio - 0.15) / 0.25
            a = int(opacity * (0.45 - 0.15 * progress))
        elif ratio < 0.55:
            # Center: lightest zone to show product
            a = int(opacity * 0.30)
        else:
            # Bottom half: smooth ramp up to dark for text
            progress = (ratio - 0.55) / 0.45
            a = int(opacity * (0.30 + 0.60 * (progress ** 0.7)))
        draw.line([(0, y_pos), (w, y_pos)], fill=(0, 0, 0, a))
    base_rgba = base.convert("RGBA")
    result = Image.alpha_composite(base_rgba, overlay)
    return result.convert("RGB")


def _paste_logo(img: Image.Image, logo_path: Optional[Path], position: str,
                max_ratio: float = 0.22, margin_ratio: float = 0.04):
    if not logo_path:
        return
    logo = _open_image(logo_path)
    if not logo:
        return
    logo = logo.convert("RGBA")
    w, h = img.size
    max_w = int(w * max_ratio)
    max_h = int(h * 0.07)
    scale = min(max_w / logo.width, max_h / logo.height)
    nw, nh = max(1, int(logo.width * scale)), max(1, int(logo.height * scale))
    logo = logo.resize((nw, nh), Image.LANCZOS)

    margin = int(w * margin_ratio)
    if position == "top-center":
        x, y = (w - nw) // 2, margin
    elif position == "bottom-right":
        x, y = w - nw - margin, h - nh - margin
    elif position == "bottom-left":
        x, y = margin, h - nh - margin
    else:
        x, y = margin, margin

    img_rgba = img.convert("RGBA")
    img_rgba.paste(logo, (x, y), logo)
    img.paste(img_rgba.convert("RGB"))


# ── Main composition ─────────────────────────────────────────────────

def compose_premium(
    brand: Brand, fmt: ContentFormat, headline: str, body: str = "",
    *, product=None, photo_index: int = 0, quality: str = "draft",
) -> str:
    size = FORMAT_SIZE[fmt]
    w, h = size

    photo_path = _pick_photo(product, photo_index)
    if photo_path:
        bg = _open_image(photo_path)
        if bg:
            bg = bg.convert("RGB")
            bg = _cover(bg, size)
        else:
            bg = Image.new("RGB", size, "#1a1a1a")
    else:
        bg = Image.new("RGB", size, "#1a1a1a")

    bg = _overlay_gradient(bg, opacity=190)
    draw = ImageDraw.Draw(bg)
    margin = int(w * 0.08)
    content_w = w - margin * 2

    # ── Logo principal (clair) en haut au centre ──
    logo_light = _get_logo(brand, "light")
    _paste_logo(bg, logo_light, "top-center", max_ratio=0.35, margin_ratio=0.035)
    draw = ImageDraw.Draw(bg)

    # ── Nom de marque espacé sous le logo ──
    brand_font = _font("semibold", int(w * 0.028))
    spaced = "   ".join(brand.name.upper())
    brand_y = int(h * 0.10)
    _draw_centered(draw, spaced, brand_font, brand_y, w, fill=(255, 255, 255, 200))

    # ── Headline bold dans la zone basse ──
    hl_len = len(headline)
    if hl_len < 40:
        hl_size = int(w * 0.09)
    elif hl_len < 80:
        hl_size = int(w * 0.07)
    else:
        hl_size = int(w * 0.055)

    hl_font = _font("bold", hl_size)
    hl_y = int(h * 0.58)
    hl_end = _draw_multiline_centered(
        draw, headline, hl_font, hl_y, w, content_w,
        fill=(255, 255, 255, 255), line_spacing=1.15,
    )

    # ── Body / sous-titre ──
    if body:
        body_font = _font("light", int(w * 0.032))
        body_y = hl_end + int(h * 0.02)
        _draw_multiline_centered(
            draw, body, body_font, body_y, w, content_w,
            fill=(255, 255, 255, 180),
        )

    # ── Footer : site web ──
    website = brand.website_url or ""
    if website:
        display = website.replace("https://", "").replace("http://", "").rstrip("/")
        footer_font = _font("regular", int(w * 0.022))
        footer_y = h - int(h * 0.045)
        _draw_centered(draw, display.upper(), footer_font, footer_y, w,
                       fill=(255, 255, 255, 130))

    # ── Logo secondaire en bas à droite ──
    logo_sec = _get_logo(brand, "secondary-light") or _get_logo(brand, "secondary")
    _paste_logo(bg, logo_sec, "bottom-right", max_ratio=0.10, margin_ratio=0.04)

    return _save(bg)


def compose_slide(
    brand: Brand, fmt: ContentFormat, headline: str, body: str = "",
    *, brief: str = "", angle: str = "", generate_ai_image: bool = True,
    product=None, quality: str = "draft", slide_index: int = 0,
) -> str:
    product_images = _get_product_images(product)

    if product_images:
        return compose_premium(
            brand, fmt, headline, body,
            product=product, photo_index=slide_index, quality=quality,
        )

    if generate_ai_image and settings.has_image_ai:
        product_name = getattr(product, "name", "") if product else ""
        ai_path = generate_full_visual(
            brand, headline, body, angle, fmt,
            product_name=product_name, quality=quality,
        )
        if ai_path:
            img = _open_image(MEDIA_DIR / Path(ai_path).name)
            if img:
                img = img.convert("RGB")
                img = _cover(img, FORMAT_SIZE[fmt])
                return _save(img)

    return compose_premium(
        brand, fmt, headline, body,
        product=product, photo_index=slide_index, quality=quality,
    )


def compose_content(
    brand: Brand, content, use_ai_image: Optional[bool] = None,
    quality: str = "draft",
) -> List[str]:
    fmt = content.format
    paths = []
    gen_ai = settings.has_image_ai if use_ai_image is None else (
        use_ai_image and settings.has_image_ai
    )
    product = getattr(content, "product", None)

    if fmt == ContentFormat.CAROUSEL and content.slides:
        for i, slide in enumerate(content.slides):
            paths.append(compose_slide(
                brand, fmt,
                slide.get("headline", ""),
                slide.get("body", ""),
                brief=content.prompt, angle=content.angle,
                generate_ai_image=gen_ai, product=product,
                quality=quality, slide_index=i,
            ))
    elif fmt == ContentFormat.STORY:
        slide = (content.slides or [{}])[0]
        paths.append(compose_slide(
            brand, fmt,
            slide.get("headline", content.hook),
            slide.get("body", ""),
            brief=content.prompt, angle=content.angle,
            generate_ai_image=gen_ai, product=product,
            quality=quality,
        ))
    else:
        paths.append(compose_slide(
            brand, fmt, content.hook, "",
            brief=content.prompt, angle=content.angle,
            generate_ai_image=gen_ai, product=product,
            quality=quality,
        ))
    return paths
