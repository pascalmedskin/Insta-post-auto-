"""Connexion Instagram via Meta OAuth (Facebook Login).

Flux :
  1. GET  /api/instagram/auth-url?brand_id=X  → URL de login Facebook
  2. GET  /api/instagram/callback?code=...&state=brand_id  → échange token
  3. GET  /api/instagram/status?brand_id=X  → statut de connexion
  4. POST /api/instagram/disconnect?brand_id=X  → déconnexion
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Brand

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instagram", tags=["instagram"])

_SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
_GRAPH = f"https://graph.facebook.com/{settings.ig_graph_version}"


def _redirect_uri() -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/instagram/callback"


@router.get("/auth-url")
def auth_url(brand_id: int):
    if not settings.has_meta_oauth:
        raise HTTPException(400, "META_APP_ID et META_APP_SECRET non configurés dans .env")
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": _redirect_uri(),
        "scope": _SCOPES,
        "response_type": "code",
        "state": str(brand_id),
    }
    url = f"https://www.facebook.com/{settings.ig_graph_version}/dialog/oauth?{urlencode(params)}"
    return {"url": url}


@router.get("/callback")
def callback(code: str, state: str = "0", db: Session = Depends(get_db)):
    brand_id = int(state)
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")

    try:
        short_token = _exchange_code(code)
        long_token = _exchange_long_lived(short_token)
        page_token, page_id = _get_page_token(long_token)
        ig_user_id, ig_username = _get_ig_account(page_id, page_token)
    except Exception as exc:
        logger.exception("Instagram OAuth failed")
        return HTMLResponse(_result_page(False, str(exc)), status_code=200)

    brand.ig_access_token = page_token
    brand.ig_user_id = ig_user_id
    brand.ig_username = ig_username
    db.commit()

    return HTMLResponse(_result_page(True, ig_username))


@router.get("/status")
def status(brand_id: int, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")
    connected = bool(brand.ig_access_token and brand.ig_user_id)
    return {
        "connected": connected,
        "username": brand.ig_username or "",
        "user_id": brand.ig_user_id or "",
        "meta_oauth_available": settings.has_meta_oauth,
    }


@router.post("/connect-token")
def connect_token(brand_id: int, payload: dict, db: Session = Depends(get_db)):
    """Connexion directe avec un access token collé par l'utilisateur."""
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")
    token = payload.get("token", "").strip()
    if not token:
        raise HTTPException(400, "Token manquant")

    try:
        page_token, page_id = _get_page_token(token)
        ig_user_id, ig_username = _get_ig_account(page_id, page_token)
    except Exception as exc:
        logger.exception("Instagram token connect failed")
        raise HTTPException(400, str(exc)) from exc

    brand.ig_access_token = page_token
    brand.ig_user_id = ig_user_id
    brand.ig_username = ig_username
    db.commit()
    return {"ok": True, "username": ig_username}


@router.post("/save-app-config")
def save_app_config(payload: dict):
    """Sauvegarde META_APP_ID et META_APP_SECRET dans le .env (admin, une seule fois)."""
    app_id = payload.get("app_id", "").strip()
    app_secret = payload.get("app_secret", "").strip()
    if not app_id or not app_secret:
        raise HTTPException(400, "App ID et App Secret requis")

    from app.config import BASE_DIR
    env_path = BASE_DIR / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    keys_done = set()
    new_lines = []
    for line in lines:
        if line.startswith("META_APP_ID="):
            new_lines.append(f"META_APP_ID={app_id}")
            keys_done.add("META_APP_ID")
        elif line.startswith("META_APP_SECRET="):
            new_lines.append(f"META_APP_SECRET={app_secret}")
            keys_done.add("META_APP_SECRET")
        else:
            new_lines.append(line)
    if "META_APP_ID" not in keys_done:
        new_lines.append(f"META_APP_ID={app_id}")
    if "META_APP_SECRET" not in keys_done:
        new_lines.append(f"META_APP_SECRET={app_secret}")

    env_path.write_text("\n".join(new_lines) + "\n")

    settings.meta_app_id = app_id
    settings.meta_app_secret = app_secret

    return {"ok": True}


@router.post("/disconnect")
def disconnect(brand_id: int, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")
    brand.ig_access_token = ""
    brand.ig_user_id = ""
    brand.ig_username = ""
    db.commit()
    return {"ok": True}


# ── Meta Graph helpers ────────────────────────────────────────────────

def _exchange_code(code: str) -> str:
    resp = httpx.get(f"{_GRAPH}/oauth/access_token", params={
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "redirect_uri": _redirect_uri(),
        "code": code,
    }, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data["access_token"]


def _exchange_long_lived(short_token: str) -> str:
    resp = httpx.get(f"{_GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "fb_exchange_token": short_token,
    }, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data["access_token"]


def _get_page_token(user_token: str) -> tuple:
    resp = httpx.get(f"{_GRAPH}/me/accounts", params={
        "access_token": user_token,
        "fields": "id,name,access_token,instagram_business_account",
    }, timeout=30)
    data = resp.json()
    pages = data.get("data", [])
    if not pages:
        raise RuntimeError("Aucune page Facebook trouvée. Lie une Page Facebook à ton compte Instagram Business.")

    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            return page["access_token"], page["id"]

    raise RuntimeError(
        "Aucune page Facebook n'est liée à un compte Instagram Business. "
        "Va dans les paramètres de ta page Facebook → Instagram → Connecte ton compte."
    )


def _get_ig_account(page_id: str, page_token: str) -> tuple:
    resp = httpx.get(f"{_GRAPH}/{page_id}", params={
        "fields": "instagram_business_account",
        "access_token": page_token,
    }, timeout=30)
    data = resp.json()
    ig = data.get("instagram_business_account", {})
    ig_id = ig.get("id", "")
    if not ig_id:
        raise RuntimeError("Compte Instagram Business introuvable sur cette page.")

    resp2 = httpx.get(f"{_GRAPH}/{ig_id}", params={
        "fields": "id,username",
        "access_token": page_token,
    }, timeout=30)
    ig_data = resp2.json()
    return ig_data.get("id", ig_id), ig_data.get("username", "")


def _result_page(success: bool, detail: str) -> str:
    if success:
        title = "Instagram connecté"
        msg = f"Compte @{detail} connecté avec succès."
        color = "#22c55e"
        icon = "✓"
    else:
        title = "Erreur de connexion"
        msg = f"Impossible de connecter Instagram : {detail}"
        color = "#ef4444"
        icon = "✕"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body {{ background:#000; color:#fff; font-family:-apple-system,system-ui,sans-serif;
         display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; }}
  .card {{ text-align:center; padding:40px; max-width:400px; }}
  .icon {{ width:64px; height:64px; border-radius:50%; background:{color}; color:#fff;
           display:flex; align-items:center; justify-content:center; font-size:32px;
           margin:0 auto 20px; }}
  h1 {{ font-size:1.25rem; margin:0 0 8px; }}
  p {{ color:#aaa; font-size:.875rem; margin:0 0 24px; }}
  a {{ display:inline-block; padding:12px 32px; background:#0095f6; color:#fff;
       border-radius:8px; text-decoration:none; font-weight:600; }}
</style></head>
<body><div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{msg}</p>
  <a href="/">Retour à l'app</a>
  <script>if(window.opener){{window.opener.postMessage({{igConnected:{str(success).lower()}}}, '*');setTimeout(()=>window.close(),1500);}}</script>
</div></body></html>"""
