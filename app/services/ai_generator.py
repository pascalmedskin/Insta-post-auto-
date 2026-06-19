"""Génération de copy Instagram via Claude.

Produit N déclinaisons d'un même brief, chacune avec un *angle d'attaque*
différent (pain point, curiosité, preuve sociale, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

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


LANG_NAMES = {
    "fr": "français", "de": "allemand", "en": "anglais", "it": "italien",
    "es": "espagnol", "pt": "portugais", "nl": "néerlandais", "ja": "japonais",
    "zh": "chinois", "ko": "coréen", "ar": "arabe", "ru": "russe",
}


def _build_prompt(
    brand: Brand, brief: str, fmt: ContentFormat, n: int, language: str = "fr"
) -> tuple[str, str]:
    angles = ATTACK_ANGLES[:n] if n <= len(ATTACK_ANGLES) else ATTACK_ANGLES
    chosen = [angles[i % len(angles)] for i in range(n)]
    angles_block = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(chosen))

    lang_name = LANG_NAMES.get(language, language)
    lang_instruction = f"\n\nIMPORTANT : Tout le contenu (hooks, captions, hashtags, slides) DOIT être rédigé en **{lang_name}**." if language != "fr" else ""

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
- "slides" : selon le format (voir consigne ci-dessus){lang_instruction}

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
    brand: Brand, brief: str, fmt: ContentFormat, n: int = 10, language: str = "fr"
) -> list[dict]:
    """Retourne une liste de dicts {angle, hook, caption, hashtags, slides}."""
    if not settings.has_text_ai:
        logger.warning("ANTHROPIC_API_KEY absente — génération en mode démo.")
        return _fallback_variations(brand, brief, fmt, n)

    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    system, user = _build_prompt(brand, brief, fmt, n, language=language)

    resp = client.messages.create(
        model=settings.text_model,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()

    # Claude peut entourer le JSON de ```json … ``` : on nettoie.
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                raw = stripped
                break

    # Tronquer les caractères invalides après le JSON fermant
    depth = 0
    end = 0
    for i, c in enumerate(raw):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end:
        raw = raw[:end]

    try:
        data = json.loads(raw)
        variations = data.get("variations", [])
    except (json.JSONDecodeError, AttributeError):
        logger.exception("Réponse Claude non parsable, fallback. Brut: %s", raw[:500])
        return _fallback_variations(brand, brief, fmt, n)

    # Normalise les champs manquants.
    for v in variations:
        v.setdefault("angle", "")
        v.setdefault("hook", "")
        v.setdefault("caption", "")
        v.setdefault("hashtags", brand.default_hashtags or "")
        v.setdefault("slides", [])
    return variations[:n] or _fallback_variations(brand, brief, fmt, n)


def extract_single_product(page_text: str, brand_name: str = "", languages: list[str] | None = None) -> dict:
    """Analyse le texte d'une page produit et extrait les infos structurées."""
    if not languages:
        languages = ["fr"]
    if not settings.has_text_ai:
        return {"name": "Produit", "description": page_text[:300], "descriptions": {languages[0]: page_text[:300]}}

    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)

    lang_list = ", ".join(f'"{l}"' for l in languages)
    desc_example = ", ".join(f'"{l}": "description en {l}..."' for l in languages)

    resp = client.messages.create(
        model=settings.text_model,
        max_tokens=3000,
        system=(
            "Tu es un expert en analyse de pages produit. "
            "Extrais les informations du produit depuis le contenu de la page. "
            "Réponds UNIQUEMENT en JSON valide."
        ),
        messages=[{"role": "user", "content": f"""Marque : {brand_name}

Contenu de la page produit :
{page_text[:10000]}

Extrais les infos du produit principal de cette page.
La description doit être fournie dans TOUTES ces langues : [{lang_list}]

- name : nom commercial exact du produit (ne pas traduire)
- description : description dans la première langue ({languages[0]})
- descriptions : objet avec une description complète (3-5 phrases) dans chaque langue
- width_mm : largeur en mm si mentionnée (sinon null)
- height_mm : hauteur en mm si mentionnée (sinon null)
- depth_mm : profondeur en mm si mentionnée (sinon null)
- category : catégorie (ex: "appareil", "sérum", "crème", "machine")

JSON strict :
{{"name": "...", "description": "...", "descriptions": {{{desc_example}}}, "width_mm": null, "height_mm": null, "depth_mm": null, "category": "..."}}"""}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    try:
        if "```" in raw:
            for part in raw.split("```"):
                s = part.strip()
                if s.startswith("json"):
                    s = s[4:].strip()
                if s.startswith("{"):
                    raw = s
                    break
        depth = 0
        end = 0
        for i, c in enumerate(raw):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            raw = raw[:end]
        import json
        return json.loads(raw)
    except Exception:
        logger.exception("Échec extraction produit depuis page.")
        return {"name": "Produit", "description": page_text[:300]}


def extract_products_from_brand(
    brand_name: str,
    pdf_text: str = "",
    website_text: str = "",
) -> list[dict]:
    """Analyse le PDF et/ou le site web pour détecter les produits."""
    if not settings.has_text_ai:
        logger.warning("ANTHROPIC_API_KEY absente — extraction produits impossible.")
        return []

    if not pdf_text and not website_text:
        return []

    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)

    system = (
        "Tu es un expert en analyse de marques et catalogues produits. "
        "On te donne du contenu extrait d'un PDF de brand guidelines et/ou "
        "d'un site web. Analyse et détecte TOUS les produits/appareils/machines. "
        "Réponds UNIQUEMENT en JSON valide, sans texte autour."
    )

    sources = ""
    if pdf_text:
        sources += f"# TEXTE EXTRAIT DU PDF DE BRAND GUIDELINES\n{pdf_text[:12000]}\n\n"
    if website_text:
        sources += f"# CONTENU DU SITE WEB (PAGE PRODUITS)\n{website_text[:12000]}\n\n"

    user = f"""# MARQUE
Nom : {brand_name}

{sources}
# MISSION
Analyse ces sources et détecte tous les produits, appareils, machines,
soins ou traitements mentionnés. Pour chaque produit trouvé, extrais :

- name : le nom exact du produit/appareil (tel qu'affiché commercialement)
- description : description complète (3-5 phrases) : ce que c'est, à quoi ça sert,
  ses bénéfices clés, sa technologie si applicable
- width_mm : largeur en mm si mentionnée (sinon null)
- height_mm : hauteur en mm si mentionnée (sinon null)
- depth_mm : profondeur en mm si mentionnée (sinon null)
- category : catégorie libre (ex: "appareil", "sérum", "crème", "accessoire", "traitement", "machine")

Si aucun produit n'est mentionné, retourne un tableau vide.
Ne PAS inventer de produits non mentionnés dans les sources.
FUSIONNE les doublons (même produit PDF + site web = 1 seul produit avec description enrichie).

# SORTIE (JSON strict)
{{"products": [{{"name": "...", "description": "...", "width_mm": null,
"height_mm": null, "depth_mm": null, "category": "..."}}]}}"""

    try:
        resp = client.messages.create(
            model=settings.text_model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(block.text for block in resp.content if block.type == "text").strip()

        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    raw = stripped
                    break

        depth = 0
        end = 0
        for i, c in enumerate(raw):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            raw = raw[:end]

        data = json.loads(raw)
        return data.get("products", [])
    except Exception:
        logger.exception("Échec extraction IA des produits.")
        return []


def extract_brand_info(pdf_text: str, brand_name: str, website_url: Optional[str] = None) -> dict:
    """Analyse le texte d'un PDF de brand guidelines avec Claude et extrait
    les infos structurées de la marque."""
    if not settings.has_text_ai:
        logger.warning("ANTHROPIC_API_KEY absente — extraction IA impossible.")
        return {}

    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)

    system = (
        "Tu es un expert en branding et identité visuelle. "
        "On te donne le texte extrait d'un PDF de brand guidelines. "
        "Analyse-le et extrais les informations de la marque. "
        "Réponds UNIQUEMENT en JSON valide, sans texte autour."
    )

    user = f"""# MARQUE
Nom : {brand_name}
{f"Site web : {website_url}" if website_url else ""}

# TEXTE EXTRAIT DU PDF DE BRAND GUIDELINES
{pdf_text}

# MISSION
Analyse ce document et extrais les informations suivantes.
Pour les couleurs, cherche les codes hex mentionnés dans le document.
Si une info n'est pas trouvable, propose une valeur cohérente avec la marque.

# SORTIE (JSON strict)
{{
  "primary_color": "#XXXXXX (couleur principale de la marque)",
  "secondary_color": "#XXXXXX (couleur secondaire)",
  "accent_color": "#XXXXXX (couleur d'accentuation)",
  "tone_of_voice": "3-5 mots décrivant le ton (ex: expert, rassurant, premium)",
  "target_audience": "description courte de l'audience cible",
  "default_hashtags": "#hashtag1 #hashtag2 ... (8-12 hashtags pertinents)",
  "font_family": "nom EXACT de la police principale/titres (ex: Work Sans, Montserrat). Cherche dans le document.",
  "font_body": "nom EXACT de la police pour le corps de texte, si différente de font_family (sinon même valeur)",
  "languages": ["fr", "de", "en"],
  "guidelines": "résumé structuré des guidelines en 500 mots max, utile pour générer du contenu cohérent"
}}

IMPORTANT pour "languages" : détecte les langues utilisées dans le document et/ou
sur le site web. Exemples courants pour la Suisse : ["fr","de","en"] ou ["fr","de","it","en"].
Si tu ne peux pas détecter, mets ["fr"]."""

    try:
        resp = client.messages.create(
            model=settings.text_model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(block.text for block in resp.content if block.type == "text").strip()

        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            raw = raw[4:] if raw.lstrip().startswith("json") else raw
            raw = raw.strip("`").strip()

        return json.loads(raw)
    except Exception:
        logger.exception("Échec extraction IA des infos de marque.")
        return {}
