"""Authentification utilisateur via Facebook OAuth."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, UserSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_GRAPH = f"https://graph.facebook.com/{settings.ig_graph_version}"


def _redirect_uri() -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/auth/callback"


@router.get("/login-url")
def login_url():
    if not settings.has_meta_oauth:
        raise HTTPException(400, "META_APP_ID non configuré")
    if not settings.meta_login_config_id:
        raise HTTPException(400, "META_LOGIN_CONFIG_ID non configuré")
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "state": "login",
        "config_id": settings.meta_login_config_id,
        "scope": "openid",
    }
    url = f"https://www.facebook.com/{settings.ig_graph_version}/dialog/oauth?{urlencode(params)}"
    return {"url": url}


@router.get("/callback")
def callback(code: str, state: str = "login", db: Session = Depends(get_db)):
    try:
        token = _exchange_code(code)
        fb_user = _get_fb_user(token)
    except Exception as exc:
        logger.exception("Auth callback failed")
        return HTMLResponse(_result_page(False, str(exc)), status_code=200)

    fb_id = fb_user["id"]
    user = db.query(User).filter(User.fb_user_id == fb_id).first()
    if not user:
        user = User(
            fb_user_id=fb_id,
            name=fb_user.get("name", ""),
            picture_url=fb_user.get("picture", {}).get("data", {}).get("url", ""),
        )
        db.add(user)
        db.flush()

    session_token = secrets.token_hex(32)
    db.add(UserSession(token=session_token, user_id=user.id))
    db.commit()

    html = _result_page(True, user.name)
    response = HTMLResponse(html)
    is_secure = settings.public_base_url.startswith("https")
    response.set_cookie(
        "session_id",
        session_token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "picture_url": user.picture_url,
    }


@router.post("/logout")
def logout(session_id: str = Cookie(None), db: Session = Depends(get_db)):
    if session_id:
        sess = db.query(UserSession).filter(UserSession.token == session_id).first()
        if sess:
            db.delete(sess)
            db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("session_id", path="/")
    return response


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


def _get_fb_user(token: str) -> dict:
    resp = httpx.get(f"{_GRAPH}/me", params={
        "fields": "id,name,picture.width(200).height(200)",
        "access_token": token,
    }, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data


def _result_page(success: bool, detail: str) -> str:
    if success:
        title = "Connecté"
        msg = f"Bienvenue, {detail} !"
        color = "#22c55e"
        icon = "✓"
    else:
        title = "Erreur de connexion"
        msg = f"Impossible de se connecter : {detail}"
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
</style></head>
<body><div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{msg}</p>
  <script>
    if(window.opener){{
      window.opener.postMessage({{authSuccess:{str(success).lower()}}}, '*');
      setTimeout(()=>window.close(),1500);
    }} else {{
      setTimeout(()=>window.location.href='/',1500);
    }}
  </script>
</div></body></html>"""
