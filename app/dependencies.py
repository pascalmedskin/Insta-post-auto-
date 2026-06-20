"""Auth dependency: extracts current user from session cookie."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Brand, User, UserSession


def get_current_user(
    session_id: str = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    if not session_id:
        raise HTTPException(status_code=401, detail="Non authentifié")
    user_session = db.query(UserSession).filter(UserSession.token == session_id).first()
    if not user_session:
        raise HTTPException(status_code=401, detail="Session invalide")
    return user_session.user


def get_brand_for_user(brand_id: int, user: User, db: Session) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")
    if brand.user_id is not None and brand.user_id != user.id:
        raise HTTPException(403, "Accès refusé")
    return brand
