"""Génération de copy Instagram via Claude.

Produit N déclinaisons d'un même brief, chacune avec un *angle d'attaque*
différent (pain point, curiosité, preuve sociale, etc.).
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.models import Brand, ContentFormat

logger = logging.getLogger(__name__)

# Angles d'attaque copywriting — on cycle dessus pour varier les déclinaisons.
ATTACK_ANGLES = [
    "Pain point (mettre le doigt sur une frustration concrète)",
    "Curiosité (créer un gap d'information irrésistible)",
    "Preuve sociale (résultats, témoignages, chiffres clients)",
    "Contrarian (casser une croyance répandue)",
    "FOMO / urgence (peur de rater l'opportunité)",
    "Transformation (avant / après, promesse de changement)",
    "How-to / valeur immédiate (étapes actionnables)",
    "Storytelling (anecdote personnelle ou de marque)",
    "Statistique choc (un chiffre marquant en ouverture)",
    "Question directe (interpeller le lecteur)",
    "Erreur à éviter (ce que tout le monde fait mal)",
    "Coulisses / behind the scenes (authenticité)",
]

# Nombre de slides recommandé par format.
SLIDES_HINT = {
    ContentFormat.POST: 1,
    ContentFormat.STORY: 1,
    ContentFormat.CAROUSEL: 6,
}


def _slides_instruction(fmt: ContentFormat) -> str:
    if fmt == ContentFormat.CAROUSEL:
        return (
            "Fournis 5 à 7 slides dans `slides` (chaque slide = {headline, body}). "
            "Slide 1 = le hook visuel fort, dernière slide = call-to-action."
        )
    if fmt == ContentFormat.STORY:
        return (
            "Fournis 1 slide dans `slides` ({headline, body}) : texte ultra court, "
            "punchy, lisible en 2 secondes. Ajoute un CTA sticker-friendly."
        )
    return "Laisse `slides` vide (post simple)."


def _build_prompt(
    brand: Brand, brief: str, fmt: ContentFormat, n: int
) -> tuple[str, str]:
    angles = ATTACK_ANGLES[:n] if n <= len(ATTACK_ANGLES) else ATTACK_ANGLES
    # Si on demande plus de variations que d'angles, on recycle en boucle.
    chosen = [angles[i % len(angles)] for i in range(n)]
    angles_block = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(chosen))

    system = (
        "Tu es un expert en copywriting Instagram et growth social media. "
        "Tu écris des hooks qui stoppent le scroll et des captions qui convertissent. "
        "Tu respectes scrupuleusement la charte de marque fournie et tu réponds "
        "UNIQUEMENT en JSON valide, sans texte autour."
    )

    user = f"""# MARQUE
Nom : {brand.name}
Audience cible : {brand.target_audience or "non précisée"}
Ton de voix : {brand.tone_of_voice or "non précisé"}
Charte / ligne éditoriale :
{brand.guidelines or "(aucune)"}
Hashtags par défaut : {brand.default_hashtags or "(aucun)"}

# BRIEF
{brief}

# FORMAT : {fmt.value}
{_slides_instruction(fmt)}

# MISSION
Génère exactement {n} déclinaisons de ce contenu. Chaque déclinaison utilise
un angle d'attaque DIFFÉRENT parmi ceux-ci (dans cet ordre) :
{angles_block}

Pour chaque déclinaison, fournis :
- "angle" : le nom court de l'angle utilisé
- "hook" : la 1re ligne / accroche qui CONVERTIT (max ~120 caractères, doit
  stopper le scroll). Privilégie : chiffre concret, aversion à la perte,
  bénéfice tangible, tension. Exemples de registre attendu :
  « Tu perds chaque jour 1000 CHF sans le savoir… »,
  « 3 erreurs qui ruinent ta peau (et comment les corriger) »,
  « Ce que personne ne te dit sur… ». Pas de hook tiède ni générique.
- "caption" : la légende complète Instagram (avec sauts de ligne, émojis si
  cohérent avec le ton, CTA clair en fin)
- "hashtags" : 8 à 15 hashtags pertinents séparés par des espaces
- "slides" : selon le format (voir consigne ci-dessus)

# SORTIE (JSON strict)
{{"variations": [{{"angle": "...", "hook": "...", "caption": "...",
"hashtags": "...", "slides": [{{"headline": "...", "body": "..."}}]}}]}}
"""
    return system, user


def _fallback_variations(
    brand: Brand, brief: str, fmt: ContentFormat, n: int
) -> list[dict]:
    """Déclinaisons locales si aucune clé Claude n'est configurée (mode démo)."""
    out = []
    for i in range(n):
        angle = ATTACK_ANGLES[i % len(ATTACK_ANGLES)]
        short = angle.split(" (")[0]
        hook = f"[{short}] {brief[:80]}"
        slides = []
        if fmt == ContentFormat.CAROUSEL:
            slides = [{"headline": f"Slide {s + 1}", "body": brief} for s in range(6)]
        elif fmt == ContentFormat.STORY:
            slides = [{"headline": short, "body": brief[:120]}]
        out.append(
            {
                "angle": short,
                "hook": hook,
                "caption": f"{hook}\n\n{brief}\n\n👉 (configure ANTHROPIC_API_KEY pour de vraies déclinaisons)",
                "hashtags": brand.default_hashtags or "#brand #content #instagram",
                "slides": slides,
            }
        )
    return out


def generate_variations(
    brand: Brand, brief: str, fmt: ContentFormat, n: int = 10
) -> list[dict]:
    """Retourne une liste de dicts {angle, hook, caption, hashtags, slides}."""
    if not settings.has_text_ai:
        logger.warning("ANTHROPIC_API_KEY absente — génération en mode démo.")
        return _fallback_variations(brand, brief, fmt, n)

    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    system, user = _build_prompt(brand, brief, fmt, n)

    resp = client.messages.create(
        model=settings.text_model,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()

    # Claude peut entourer le JSON de ```json … ``` : on nettoie.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.lstrip().startswith("json") else raw
        raw = raw.strip("`").strip()

    try:
        data = json.loads(raw)
        variations = data.get("variations", [])
    except (json.JSONDecodeError, AttributeError):
        logger.exception("Réponse Claude non parsable, fallback. Brut: %s", raw[:300])
        return _fallback_variations(brand, brief, fmt, n)

    # Normalise les champs manquants.
    for v in variations:
        v.setdefault("angle", "")
        v.setdefault("hook", "")
        v.setdefault("caption", "")
        v.setdefault("hashtags", brand.default_hashtags or "")
        v.setdefault("slides", [])
    return variations[:n] or _fallback_variations(brand, brief, fmt, n)
