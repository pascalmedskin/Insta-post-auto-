"""Génération d'images IA (OpenAI gpt-image-1).

Deux modes :
- Avec photo produit → images.edit() pour préserver le produit EXACT
  et créer une mise en scène autour
- Sans photo produit → images.generate() full IA

Chaque angle d'attaque produit une mise en scène DIFFÉRENTE.
"""

from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import MEDIA_DIR, settings
from app.models import Brand, ContentFormat

logger = logging.getLogger(__name__)

FORMAT_SIZE = {
    ContentFormat.POST: (1080, 1080),
    ContentFormat.CAROUSEL: (1080, 1350),
    ContentFormat.STORY: (1080, 1920),
}

OPENAI_SIZE_DRAFT = {
    ContentFormat.POST: "1024x1024",
    ContentFormat.CAROUSEL: "1024x1536",
    ContentFormat.STORY: "1024x1536",
}

OPENAI_SIZE_HD = {
    ContentFormat.POST: "1024x1024",
    ContentFormat.CAROUSEL: "1024x1536",
    ContentFormat.STORY: "1024x1536",
}

SCENE_MOODS = {
    "pain point": (
        "Dark, dramatic chiaroscuro studio lighting with deep shadows and a single "
        "spotlight illuminating the product. Moody, cinematic atmosphere. "
        "Background: matte black with subtle smoke or mist diffusion."
    ),
    "curiosité": (
        "Bright, airy, ultra-clean minimalist setting. White marble or concrete surface. "
        "Soft diffused daylight from the left. Floating particles of light. "
        "Background: pure white gradient fading to soft grey."
    ),
    "preuve sociale": (
        "Professional clinical/medical environment. Sleek stainless steel surface, "
        "soft blue-toned ambient lighting suggesting precision and trust. "
        "Background: blurred high-end clinic or treatment room."
    ),
    "contrarian": (
        "Bold, unexpected split-lighting setup — one side warm gold, other side cool blue. "
        "Geometric shapes or abstract architectural elements in the background. "
        "Striking, editorial, fashion-photography inspired."
    ),
    "fomo": (
        "Ultra-luxurious setting: polished black reflective surface, golden rim lighting, "
        "warm amber backlighting creating an exclusive, premium atmosphere. "
        "Background: dark with subtle bokeh of warm lights like a VIP event."
    ),
    "transformation": (
        "Split composition: left side cool/clinical, right side warm/glowing. "
        "Gradient background transitioning from muted grey to radiant warm tones. "
        "Symbolizing before/after, evolution, breakthrough."
    ),
    "how-to": (
        "Clean, educational layout setting. Bright, evenly lit workspace. "
        "Subtle grid or geometric guidelines in background suggesting precision. "
        "Fresh, modern, approachable. Light grey or white environment."
    ),
    "storytelling": (
        "Warm, atmospheric setting like a luxury spa or boutique interior. "
        "Soft warm lighting, natural wood textures, linen fabrics in background. "
        "Intimate, human, inviting. Shallow depth of field."
    ),
    "statistique": (
        "Futuristic, data-driven aesthetic. Cool blue and silver tones. "
        "Subtle holographic or digital elements in background. Clean, precise, "
        "high-tech. Product lit with crisp white directional light."
    ),
    "question": (
        "Engaging, direct composition. Product centered with a radial light burst behind it. "
        "Dynamic, energetic feeling. Background: deep gradient from brand color to black "
        "with subtle lens flare."
    ),
    "erreur": (
        "Serious, authoritative setting. Dark background with precise spot lighting. "
        "Product placed on a glass surface with reflection beneath. "
        "Red/amber accent lights suggesting warning/attention."
    ),
    "coulisses": (
        "Behind-the-scenes studio setup. Raw, authentic feel with visible softbox edges, "
        "reflectors, or studio equipment slightly blurred in background. "
        "Natural, documentary-style lighting."
    ),
}

_DEFAULT_SCENE = (
    "Premium studio photography setting with three-point lighting. "
    "Elegant gradient background using brand colors. Soft shadows, "
    "perfect exposure, magazine-quality composition."
)


def _get_scene_mood(angle: str) -> str:
    angle_lower = angle.lower()
    for key, mood in SCENE_MOODS.items():
        if key in angle_lower:
            return mood
    return _DEFAULT_SCENE


def _build_edit_prompt(
    brand: Brand,
    headline: str,
    body: str,
    angle: str,
    fmt: ContentFormat,
    product_name: str = "",
    quality: str = "draft",
) -> str:
    brand_name = brand.name
    website = brand.website_url or f"{brand_name.lower().replace(' ', '-')}.ch"
    tone = brand.tone_of_voice or "premium, professional, sophisticated"
    font_display = brand.font_family or "Montserrat"
    font_body_name = brand.font_body or font_display
    guidelines = brand.guidelines or ""
    scene = _get_scene_mood(angle)

    guidelines_block = ""
    if guidelines:
        guidelines_block = (
            f"\nBRAND GUIDELINES (FOLLOW STRICTLY):\n"
            f"{guidelines[:1000]}\n"
        )

    ratio_desc = {
        ContentFormat.POST: "square 1:1",
        ContentFormat.CAROUSEL: "vertical 4:5",
        ContentFormat.STORY: "vertical 9:16",
    }[fmt]

    return (
        f"You are a world-class art director at a top creative agency (Pentagram, "
        f"R/GA, Wieden+Kennedy level). Create a stunning Instagram {fmt.value} visual "
        f"({ratio_desc}) worthy of international design awards.\n\n"

        f"CRITICAL RULE — PRODUCT INTEGRITY:\n"
        f"The image provided shows the REAL product ({product_name}). You MUST:\n"
        f"- Keep the product EXACTLY as shown — same shape, proportions, details, colors\n"
        f"- NEVER modify, reshape, redesign, or reimagine the product\n"
        f"- NEVER add fake buttons, screens, or features that don't exist\n"
        f"- The product is SACRED — only change the ENVIRONMENT around it\n\n"

        f"SCENE & MISE EN SCÈNE (unique to this variation):\n"
        f"{scene}\n\n"

        f"TYPOGRAPHY — EXACT TEXT TO RENDER:\n"
        f"- Brand name: '{brand_name.upper()}' — use {font_display} font, "
        f"elegant small-caps with wide letter-spacing, positioned at the top\n"
        f"- Main headline: \"{headline}\" — use {font_display} BOLD, very large, "
        f"prominent, the DOMINANT text element. Must be perfectly readable.\n"
        f"{'- Subtext: ' + chr(34) + body + chr(34) + ' — use ' + font_body_name + ' regular, smaller size.' + chr(10) if body else ''}"
        f"- Website: '{website}' — tiny uppercase at the bottom\n"
        f"- All text must be PERFECTLY SPELLED, character by character. "
        f"Double-check every letter.\n\n"

        f"BRAND IDENTITY (MANDATORY):\n"
        f"- Primary color: {brand.primary_color} (use for backgrounds, key elements)\n"
        f"- Secondary color: {brand.secondary_color} (use for text, accents)\n"
        f"- Accent color: {brand.accent_color} (use for CTA, highlights)\n"
        f"- Display font: {font_display} — clean, modern, premium\n"
        f"- Body font: {font_body_name}\n"
        f"- Brand tone: {tone}\n\n"

        f"QUALITY STANDARDS:\n"
        f"- This must look like a real campaign from a €100K+ production budget\n"
        f"- Perfect composition: rule of thirds, golden ratio, deliberate negative space\n"
        f"- Professional color grading matching brand palette\n"
        f"- No stock photo aesthetic — editorial, magazine-cover quality\n"
        f"- Text is PART of the design (baked in), crisp and readable\n"
        f"- {'MAXIMUM quality: 8K sharpness, micro-details, professional retouching' if quality == 'hd' else 'High quality, clean and polished'}\n"
        f"{guidelines_block}"
    )


def _build_generate_prompt(
    brand: Brand,
    headline: str,
    body: str,
    angle: str,
    fmt: ContentFormat,
    product_name: str = "",
    quality: str = "draft",
) -> str:
    brand_name = brand.name
    website = brand.website_url or f"{brand_name.lower().replace(' ', '-')}.ch"
    tone = brand.tone_of_voice or "premium, professional, sophisticated"
    font_display = brand.font_family or "Montserrat"
    font_body_name = brand.font_body or font_display
    audience = brand.target_audience or ""
    guidelines = brand.guidelines or ""
    scene = _get_scene_mood(angle)

    guidelines_block = ""
    if guidelines:
        guidelines_block = (
            f"\nBRAND GUIDELINES (FOLLOW STRICTLY):\n"
            f"{guidelines[:1000]}\n"
        )

    ratio_desc = {
        ContentFormat.POST: "square 1:1",
        ContentFormat.CAROUSEL: "vertical 4:5",
        ContentFormat.STORY: "vertical 9:16",
    }[fmt]

    return (
        f"You are a world-class art director. Create a stunning Instagram {fmt.value} "
        f"visual ({ratio_desc}) for the brand '{brand_name}' worthy of design awards.\n\n"

        f"SCENE:\n{scene}\n\n"

        f"{'PRODUCT: Feature the ' + product_name + ' as the hero, beautifully lit.' + chr(10) if product_name else ''}"

        f"TYPOGRAPHY — EXACT TEXT:\n"
        f"- Top: '{brand_name.upper()}' in {font_display}, small-caps, wide tracking\n"
        f"- Headline: \"{headline}\" in {font_display} BOLD, very large, dominant\n"
        f"{'- Body: ' + chr(34) + body + chr(34) + ' in ' + font_body_name + ', smaller' + chr(10) if body else ''}"
        f"- Footer: '{website}' tiny uppercase\n"
        f"- All text PERFECTLY SPELLED.\n\n"

        f"BRAND IDENTITY:\n"
        f"- Colors: primary {brand.primary_color}, secondary {brand.secondary_color}, "
        f"accent {brand.accent_color}\n"
        f"- Fonts: {font_display} (display), {font_body_name} (body)\n"
        f"- Tone: {tone}. {'Audience: ' + audience + '.' if audience else ''}\n\n"

        f"QUALITY: €100K+ production value. Editorial, magazine-cover quality. "
        f"No stock photo feel. Perfect composition, professional color grading.\n"
        f"{'MAXIMUM quality: 8K sharpness, micro-details.' if quality == 'hd' else ''}\n"
        f"{guidelines_block}"
    )


def generate_full_visual(
    brand: Brand,
    headline: str,
    body: str,
    angle: str,
    fmt: ContentFormat,
    product_name: str = "",
    quality: str = "draft",
    product_image_path: Optional[str] = None,
) -> Optional[str]:
    """Génère un visuel complet. Utilise images.edit() si une photo produit
    est fournie, sinon images.generate()."""
    if not settings.has_image_ai:
        return None

    size_map = OPENAI_SIZE_HD if quality == "hd" else OPENAI_SIZE_DRAFT
    size = size_map.get(fmt, "1024x1024")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        abs_image = None
        if product_image_path:
            candidate = MEDIA_DIR / Path(product_image_path).name
            if candidate.exists():
                abs_image = candidate

        if abs_image:
            prompt = _build_edit_prompt(
                brand, headline, body, angle, fmt, product_name, quality,
            )
            logger.info("Image edit avec photo produit: %s", abs_image.name)
            with open(abs_image, "rb") as img_file:
                result = client.images.edit(
                    model=settings.image_model,
                    image=img_file,
                    prompt=prompt,
                    size=size,
                    quality="high" if quality == "hd" else "auto",
                )
        else:
            prompt = _build_generate_prompt(
                brand, headline, body, angle, fmt, product_name, quality,
            )
            logger.info("Image generate (sans photo produit)")
            result = client.images.generate(
                model=settings.image_model,
                prompt=prompt,
                size=size,
                n=1,
                quality="high" if quality == "hd" else "auto",
            )

        b64 = result.data[0].b64_json
        raw = base64.b64decode(b64)
        prefix = "hd" if quality == "hd" else "draft"
        fname = f"gen_{prefix}_{uuid.uuid4().hex}.png"
        (MEDIA_DIR / fname).write_bytes(raw)
        logger.info("Visuel %s généré : %s (%s)", quality, fname, size)
        return f"media/{fname}"
    except Exception:
        logger.exception("Échec génération visuel IA.")
        return None


def generate_image(
    brand: Brand, brief: str, angle: str, fmt: ContentFormat
) -> Optional[str]:
    """Compatibilité avec l'ancien appel."""
    return generate_full_visual(brand, brief, "", angle, fmt)
