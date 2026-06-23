"""Web Push notification endpoints: VAPID key, subscribe/unsubscribe."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import get_db
from app.dependencies import get_current_user
from app.models import PushSubscription, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])

VAPID_FILE = DATA_DIR / "vapid_keys.json"


def _ensure_vapid_keys() -> dict:
    """Generate or load VAPID keys (ECDSA P-256)."""
    if VAPID_FILE.exists():
        return json.loads(VAPID_FILE.read_text())

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    import base64

    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    pub_bytes = private_key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint,
    )

    keys = {
        "public": base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode(),
        "private": base64.urlsafe_b64encode(priv_bytes).rstrip(b"=").decode(),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VAPID_FILE.write_text(json.dumps(keys))
    logger.info("Generated new VAPID keys → %s", VAPID_FILE)
    return keys


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


@router.get("/vapid-key")
def get_vapid_key():
    keys = _ensure_vapid_keys()
    return {"public_key": keys["public"]}


@router.post("/subscribe")
def subscribe(
    req: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(PushSubscription).filter_by(endpoint=req.endpoint).first()
    if existing:
        existing.p256dh = req.keys.get("p256dh", "")
        existing.auth = req.keys.get("auth", "")
    else:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=req.endpoint,
            p256dh=req.keys.get("p256dh", ""),
            auth=req.keys.get("auth", ""),
        )
        db.add(sub)
    db.commit()
    return {"ok": True}


@router.delete("/unsubscribe")
def unsubscribe(
    req: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(PushSubscription).filter_by(endpoint=req.endpoint, user_id=user.id).first()
    if sub:
        db.delete(sub)
        db.commit()
    return {"ok": True}


def send_push_to_user(user_id: int, title: str, body: str, url: str = "/", db_session=None) -> int:
    """Send push notification to all subscriptions for a user. Returns count sent."""
    from pywebpush import webpush, WebPushException

    keys = _ensure_vapid_keys()
    close_db = False
    if db_session is None:
        from app.database import SessionLocal
        db_session = SessionLocal()
        close_db = True

    try:
        subs = db_session.query(PushSubscription).filter_by(user_id=user_id).all()
        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=json.dumps({"title": title, "body": body, "url": url, "tag": f"reminder-{user_id}"}),
                    vapid_private_key=keys["private"],
                    vapid_claims={"sub": "mailto:noreply@instapostauto.app"},
                )
                sent += 1
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    db_session.delete(sub)
                    db_session.commit()
                    logger.info("Removed expired push subscription %s", sub.endpoint[:60])
                else:
                    logger.warning("Push failed for %s: %s", sub.endpoint[:60], e)
            except Exception as e:
                logger.warning("Push error: %s", e)
        return sent
    finally:
        if close_db:
            db_session.close()
