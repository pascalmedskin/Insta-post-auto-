"""Connexion Instagram via Meta OAuth (Facebook Login).

Flux :
  1. GET  /api/instagram/auth-url?brand_id=X  → URL de login Facebook
  2. GET  /api/instagram/callback?code=...&state=brand_id  → échange token
  3. GET  /api/instagram/status?brand_id=X  → statut de connexion
  4. POST /api/instagram/disconnect?brand_id=X  → déconnexion
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_brand_for_user
from app.models import Brand, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instagram", tags=["instagram"])

_SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
_GRAPH = f"https://graph.facebook.com/{settings.ig_graph_version}"


def _redirect_uri() -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/instagram/callback"


@router.get("/auth-url")
def auth_url(brand_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_brand_for_user(brand_id, user, db)
    if not settings.has_meta_oauth:
        raise HTTPException(400, "META_APP_ID et META_APP_SECRET non configurés dans .env")
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "state": str(brand_id),
    }
    # Facebook Login for Business (apps « Entreprise ») : on passe par un
    # config_id qui porte les permissions. Sinon, fallback sur le scope classique.
    if settings.meta_login_config_id:
        params["config_id"] = settings.meta_login_config_id
        params["scope"] = "openid"
    else:
        params["scope"] = _SCOPES
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
    except Exception as exc:
        logger.exception("Instagram OAuth token exchange failed")
        return HTMLResponse(_result_page(False, f"Échange de token échoué : {exc}"), status_code=200)

    # Debug: check who this token belongs to and what /me/accounts returns raw
    try:
        me_resp = httpx.get(f"{_GRAPH}/me", params={
            "access_token": long_token,
            "fields": "id,name",
        }, timeout=10)
        me_data = me_resp.json()
    except Exception:
        me_data = {"error": "failed to call /me"}

    try:
        accounts_resp = httpx.get(f"{_GRAPH}/me/accounts", params={
            "access_token": long_token,
            "fields": "id,name,access_token,instagram_business_account",
        }, timeout=30)
        accounts_raw = accounts_resp.json()
    except Exception as exc:
        logger.exception("Instagram /me/accounts failed")
        return HTMLResponse(_result_page(False, f"Erreur /me/accounts : {exc}"), status_code=200)

    # Also try with short token
    try:
        accounts_short_resp = httpx.get(f"{_GRAPH}/me/accounts", params={
            "access_token": short_token,
            "fields": "id,name,access_token,instagram_business_account",
        }, timeout=30)
        accounts_short_raw = accounts_short_resp.json()
    except Exception:
        accounts_short_raw = {"error": "failed"}

    pages = accounts_raw.get("data", [])
    ig_pages = []
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            ig_id = ig.get("id", "")
            try:
                resp2 = httpx.get(f"{_GRAPH}/{ig_id}", params={
                    "fields": "id,username",
                    "access_token": page["access_token"],
                }, timeout=30)
                ig_data = resp2.json()
                username = ig_data.get("username", "")
            except Exception:
                username = ""
            ig_pages.append({
                "page_id": page["id"],
                "page_name": page.get("name", ""),
                "page_token": page["access_token"],
                "ig_user_id": ig_id,
                "ig_username": username,
            })

    if not ig_pages:
        perms = _get_token_permissions(long_token)
        perms_str = ", ".join(perms) if perms else "(aucune)"
        pages_long = len(accounts_raw.get("data", []))
        pages_short = len(accounts_short_raw.get("data", []))

        detail = (
            f"DEBUG — /me = {me_data.get('name', '?')} (id: {me_data.get('id', '?')}). "
            f"Permissions : {perms_str}. "
            f"/me/accounts (long token) : {pages_long} page(s). "
            f"/me/accounts (short token) : {pages_short} page(s). "
        )
        if "error" in accounts_raw:
            detail += f"Erreur API : {accounts_raw['error'].get('message', str(accounts_raw['error']))}. "
        if pages_long == 0 and pages_short == 0:
            detail += (
                "Le token a les permissions mais Facebook ne retourne aucune page. "
                "Vérifie que tu es admin/éditeur de tes Pages Facebook "
                "et que l'app Meta est en mode Live (pas Development)."
            )
        elif pages_long > 0 or pages_short > 0:
            all_names = [p.get("name", "?") for p in (accounts_raw if pages_long else accounts_short_raw).get("data", [])]
            detail += f"Pages : {', '.join(all_names)}. Aucune n'a d'Instagram Business lié."

        return HTMLResponse(_result_page(False, detail), status_code=200)

    if len(ig_pages) == 1:
        # Single page — auto-connect
        p = ig_pages[0]
        brand.ig_access_token = p["page_token"]
        brand.ig_user_id = p["ig_user_id"]
        brand.ig_username = p["ig_username"]
        db.commit()
        return HTMLResponse(_result_page(True, p["ig_username"]))

    # Multiple pages — show selection UI
    # Store long_token temporarily on the brand so select-page can use it
    brand.ig_access_token = f"pending:{long_token}"
    db.commit()
    return HTMLResponse(_select_page(brand_id, ig_pages))


@router.get("/status")
def status(brand_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    brand = get_brand_for_user(brand_id, user, db)
    connected = bool(brand.ig_access_token and brand.ig_user_id)
    return {
        "connected": connected,
        "username": brand.ig_username or "",
        "user_id": brand.ig_user_id or "",
        "meta_oauth_available": settings.has_meta_oauth,
    }


@router.post("/connect-token")
def connect_token(brand_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Connexion directe avec un access token collé par l'utilisateur."""
    brand = get_brand_for_user(brand_id, user, db)
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


@router.get("/debug")
def debug_connection(brand_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Diagnostic complet de la connexion Instagram — montre chaque étape."""
    brand = get_brand_for_user(brand_id, user, db)
    result = {
        "brand_id": brand.id,
        "brand_name": brand.name,
        "public_base_url": settings.public_base_url,
        "ig_graph_version": settings.ig_graph_version,
        "meta_app_id": settings.meta_app_id[:6] + "..." if settings.meta_app_id else "(vide)",
        "meta_app_secret": "***" if settings.meta_app_secret else "(vide)",
        "meta_login_config_id": settings.meta_login_config_id or "(vide)",
        "redirect_uri_auth": f"{settings.public_base_url.rstrip('/')}/api/auth/callback",
        "redirect_uri_instagram": _redirect_uri(),
        "stored_ig_user_id": brand.ig_user_id or "(vide)",
        "stored_ig_username": brand.ig_username or "(vide)",
        "stored_token_status": "pending" if (brand.ig_access_token or "").startswith("pending:") else ("set" if brand.ig_access_token else "vide"),
    }

    if brand.ig_access_token and not brand.ig_access_token.startswith("pending:"):
        try:
            resp = httpx.get(f"{_GRAPH}/me", params={
                "access_token": brand.ig_access_token,
                "fields": "id,name",
            }, timeout=10)
            data = resp.json()
            if "error" in data:
                result["token_test"] = f"INVALIDE: {data['error'].get('message', '')}"
            else:
                result["token_test"] = f"OK (page: {data.get('name', data.get('id', '?'))})"
        except Exception as e:
            result["token_test"] = f"ERREUR: {e}"

        if brand.ig_user_id:
            try:
                resp2 = httpx.get(f"{_GRAPH}/{brand.ig_user_id}", params={
                    "access_token": brand.ig_access_token,
                    "fields": "id,username,followers_count",
                }, timeout=10)
                data2 = resp2.json()
                if "error" in data2:
                    result["ig_api_test"] = f"INVALIDE: {data2['error'].get('message', '')}"
                else:
                    result["ig_api_test"] = f"OK (@{data2.get('username', '?')}, {data2.get('followers_count', '?')} followers)"
            except Exception as e:
                result["ig_api_test"] = f"ERREUR: {e}"

    result["note"] = (
        "IMPORTANT: Les 2 redirect URIs ci-dessus doivent être dans les 'URI de redirection OAuth valides' "
        "de ton app Meta (developers.facebook.com → Ton app → Facebook Login → Paramètres)."
    )

    return result


@router.post("/disconnect")
def disconnect(brand_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    brand = get_brand_for_user(brand_id, user, db)
    brand.ig_access_token = ""
    brand.ig_user_id = ""
    brand.ig_username = ""
    db.commit()
    return {"ok": True}


@router.post("/select-page")
def select_page(brand_id: int, page_id: str, db: Session = Depends(get_db)):
    """User chose a specific page from the multi-page selection UI."""
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")

    stored = brand.ig_access_token or ""
    if not stored.startswith("pending:"):
        raise HTTPException(400, "Pas de sélection en cours")

    long_token = stored.replace("pending:", "", 1)

    try:
        ig_pages = _get_all_ig_pages(long_token)
        chosen = next((p for p in ig_pages if p["page_id"] == page_id), None)
        if not chosen:
            raise HTTPException(400, "Page introuvable")

        brand.ig_access_token = chosen["page_token"]
        brand.ig_user_id = chosen["ig_user_id"]
        brand.ig_username = chosen["ig_username"]
        db.commit()
        return {"ok": True, "username": chosen["ig_username"]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Page selection failed")
        brand.ig_access_token = ""
        db.commit()
        raise HTTPException(400, str(exc)) from exc


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
    if "error" in data:
        raise RuntimeError(f"Erreur API Facebook : {data['error'].get('message', str(data['error']))}")
    pages = data.get("data", [])
    if not pages:
        raise RuntimeError("Aucune page Facebook trouvée. Vérifie que ton token a la permission pages_show_list.")

    page_names = [p.get("name", "?") for p in pages]
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            return page["access_token"], page["id"]

    raise RuntimeError(
        f"Pages trouvées ({', '.join(page_names)}) mais aucune n'a de compte Instagram Business lié. "
        "Va dans les paramètres de ta Page Facebook → Comptes liés → Instagram."
    )


def _get_token_permissions(user_token: str) -> list[str]:
    """Check which permissions the token actually has."""
    try:
        resp = httpx.get(f"{_GRAPH}/me/permissions", params={
            "access_token": user_token,
        }, timeout=10)
        data = resp.json()
        if "error" in data:
            logger.error("Permission check failed: %s", data["error"])
            return [f"ERREUR: {data['error'].get('message', '?')}"]
        perms = data.get("data", [])
        return [p["permission"] for p in perms if p.get("status") == "granted"]
    except Exception as e:
        return [f"ERREUR: {e}"]


def _get_all_pages_debug(user_token: str) -> list[dict]:
    """Return all Facebook Pages (even those without IG) for debug."""
    try:
        resp = httpx.get(f"{_GRAPH}/me/accounts", params={
            "access_token": user_token,
            "fields": "id,name",
        }, timeout=30)
        data = resp.json()
        return data.get("data", [])
    except Exception:
        return []


def _get_all_ig_pages(user_token: str) -> list[dict]:
    """Return all Facebook Pages that have an Instagram Business account."""
    resp = httpx.get(f"{_GRAPH}/me/accounts", params={
        "access_token": user_token,
        "fields": "id,name,access_token,instagram_business_account",
    }, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"API Facebook /me/accounts : {data['error'].get('message', str(data['error']))}")
    pages = data.get("data", [])
    logger.info("Facebook /me/accounts returned %d pages", len(pages))
    results = []
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            ig_id = ig.get("id", "")
            # Get username
            try:
                resp2 = httpx.get(f"{_GRAPH}/{ig_id}", params={
                    "fields": "id,username",
                    "access_token": page["access_token"],
                }, timeout=30)
                ig_data = resp2.json()
                username = ig_data.get("username", "")
            except Exception:
                username = ""
            results.append({
                "page_id": page["id"],
                "page_name": page.get("name", ""),
                "page_token": page["access_token"],
                "ig_user_id": ig_id,
                "ig_username": username,
            })
    return results


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
  .card {{ text-align:center; padding:40px 20px; max-width:500px; }}
  .icon {{ width:64px; height:64px; border-radius:50%; background:{color}; color:#fff;
           display:flex; align-items:center; justify-content:center; font-size:32px;
           margin:0 auto 20px; }}
  h1 {{ font-size:1.25rem; margin:0 0 8px; }}
  p {{ color:#aaa; font-size:.875rem; margin:0 0 24px; line-height:1.5; text-align:left; }}
  a {{ display:inline-block; padding:12px 32px; background:#0095f6; color:#fff;
       border-radius:8px; text-decoration:none; font-weight:600; }}
</style></head>
<body><div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{msg}</p>
  <a href="/">Retour à l'app</a>
  <script>
    if(window.opener){{
      window.opener.postMessage({{igConnected:{str(success).lower()}, igError:{json.dumps('' if success else detail)}}}, '*');
      {'setTimeout(()=>window.close(),1500);' if success else '// Erreur : on ne ferme PAS le popup pour que le user puisse lire'}
    }}
  </script>
</div></body></html>"""


def _select_page(brand_id: int, pages: list[dict]) -> str:
    """HTML page letting the user pick which Instagram account to connect."""
    items = ""
    for p in pages:
        page_name = p["page_name"].replace("'", "&#39;").replace('"', "&quot;")
        ig_username = p["ig_username"].replace("'", "&#39;").replace('"', "&quot;")
        items += f"""
        <button class="page-option" onclick="selectPage('{p["page_id"]}')">
          <div class="page-option-name">{page_name}</div>
          <div class="page-option-ig">@{ig_username}</div>
        </button>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Choisir un compte</title>
<style>
  body {{ background:#000; color:#fff; font-family:-apple-system,system-ui,sans-serif;
         display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; }}
  .card {{ text-align:center; padding:40px 20px; max-width:400px; width:100%; }}
  h1 {{ font-size:1.25rem; margin:0 0 8px; }}
  p {{ color:#aaa; font-size:.875rem; margin:0 0 20px; }}
  .page-option {{
    display:block; width:100%; padding:16px; margin:8px 0;
    background:#1a1a1a; border:1px solid #333; border-radius:12px;
    cursor:pointer; text-align:left; color:#fff; font-family:inherit;
    transition: border-color .15s;
  }}
  .page-option:hover {{ border-color:#0095f6; }}
  .page-option-name {{ font-weight:600; font-size:.9375rem; margin-bottom:4px; }}
  .page-option-ig {{ color:#0095f6; font-size:.8125rem; }}
</style></head>
<body><div class="card">
  <h1>Choisir un compte Instagram</h1>
  <p>Plusieurs pages Facebook sont liées à un compte Instagram. Choisis celle que tu veux utiliser :</p>
  {items}
  <script>
    function selectPage(pageId) {{
      fetch('/api/instagram/select-page?brand_id={brand_id}&page_id=' + pageId, {{method:'POST'}})
        .then(r => r.json())
        .then(data => {{
          if (data.ok && window.opener) {{
            window.opener.postMessage({{igConnected:true}}, '*');
            setTimeout(() => window.close(), 800);
          }} else if (data.ok) {{
            window.location.href = '/';
          }} else {{
            alert(data.detail || 'Erreur');
          }}
        }})
        .catch(err => alert(err.message));
    }}
  </script>
</div></body></html>"""
