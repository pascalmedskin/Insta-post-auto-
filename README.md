# 📸 Insta Post Auto

Application pour **stocker une identité de marque**, **générer du contenu Instagram**
(posts, carousels, stories) avec des **hooks qui convertissent** et des **angles
d'attaque variés**, composer les visuels (image IA + charte + mockups produits),
puis **auto-publier** selon un planning quotidien via l'**API Graph officielle**.

## ✨ Fonctionnalités

- **Marque & charte** : couleurs, polices, ton de voix, audience, hashtags.
  - Import des **brand guidelines en PDF** (texte extrait automatiquement).
  - Upload de **logos PNG** individuels + choix du logo principal.
  - Image de marque de fond.
- **Produits & mockups** : upload d'images produit avec **dimensions réelles
  (largeur × hauteur en mm)** — les mockups respectent les proportions.
- **Génération en 2 étapes** :
  1. **Hooks** qui convertissent (≥10 déclinaisons, un angle d'attaque par hook :
     pain point, curiosité, preuve sociale, FOMO, contrarian, transformation…).
  2. **Image** générée à partir du hook choisi (image IA optionnelle, sinon
     composition sur l'image de marque, avec mockup produit).
- **Bibliothèque** : édition du copy, validation, rendu des visuels.
- **Planning & auto-post** : programmation manuelle ou **auto-remplissage
  quotidien**. Un worker publie automatiquement à l'heure prévue.
- **UI responsive mobile-first** (navigation par onglets en bas d'écran).

## 🚀 Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis renseigne tes clés
uvicorn app.main:app --reload
```

Ouvre http://localhost:8000

> Sans clés API, l'app fonctionne en **mode démo** (hooks factices, pas d'image
> IA, pas de publication) — pratique pour explorer l'interface.

## 🔑 Configuration (`.env`)

| Variable | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` | Génération des hooks/captions (Claude). |
| `TEXT_MODEL` | Modèle Claude (défaut `claude-sonnet-4-6`). |
| `OPENAI_API_KEY` | Génération d'images IA (optionnel). |
| `IG_ACCESS_TOKEN` | Token longue durée Instagram Graph. |
| `IG_BUSINESS_ACCOUNT_ID` | ID du compte Instagram **Business/Creator**. |
| `PUBLIC_BASE_URL` | URL **publique** servant les images à l'API Graph. |
| `SCHEDULER_TIMEZONE` | Fuseau de planification (défaut `Europe/Zurich`). |
| `AUTOPOST_ENABLED` | Active le worker d'auto-post. |

### Instagram (API Graph officielle)

La publication exige un **compte Instagram Business/Creator** lié à une **Page
Facebook**, et une **app Meta** avec les permissions `instagram_basic`,
`instagram_content_publish`, `pages_read_engagement`.

⚠️ L'API Graph récupère les images via une **URL publique**. En local, expose
l'app avec un tunnel et renseigne `PUBLIC_BASE_URL` :

```bash
cloudflared tunnel --url http://localhost:8000   # ou ngrok http 8000
```

## 🗺️ Flux d'utilisation

1. **Marque** → crée la marque, ajoute logos / image / PDF guidelines.
2. **Produits** → (optionnel) ajoute tes produits avec leurs dimensions.
3. **Générer** → choisis le format, décris le brief → **hooks**.
4. **Bibliothèque** → édite, puis **génère l'image** (étape 2), valide.
5. **Planning** → auto-programme ; l'app publie chaque jour automatiquement.

## 🏗️ Architecture

```
app/
  main.py            FastAPI + UI + scheduler
  config.py          settings (.env)
  database.py        SQLAlchemy / SQLite
  models.py          Brand, Product, ContentItem, ScheduledPost
  schemas.py         Pydantic
  routers/           brands, products, content, schedule
  services/
    ai_generator.py  hooks/captions via Claude (+ angles d'attaque)
    image_gen.py     génération d'images IA (OpenAI)
    composer.py      composition Pillow (texte + logo + mockup produit)
    instagram.py     publication API Graph (post / carousel / story)
    scheduler.py     worker auto-post (APScheduler)
    pdf_import.py    extraction texte des guidelines PDF
    storage.py       upload de fichiers
  static/            UI mobile-first (index.html, app.js, styles.css)
```

## 📝 Notes

- Stockage local SQLite (`data/app.db`) + médias dans `app/static/media/`.
- Le scheduler tourne dans le process : garde l'app lancée pour l'auto-post
  (ou déploie sur un serveur/conteneur qui reste up).
