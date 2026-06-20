"""Endpoints de planification : créneau manuel + auto-remplissage quotidien."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_brand_for_user
from app.models import ContentItem, ContentStatus, ScheduledPost, Brand, User
from app.schemas import AutoScheduleRequest, ScheduleOut, ScheduleRequest

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _to_utc_naive(dt: datetime) -> datetime:
    """Normalise un datetime (aware ou non) en UTC naïf pour la comparaison."""
    if dt.tzinfo is None:
        # Supposé exprimé dans le fuseau du scheduler.
        dt = dt.replace(tzinfo=ZoneInfo(settings.scheduler_timezone))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _attach(content: ContentItem, when_utc: datetime, db: Session) -> ScheduledPost:
    if content.schedule:
        content.schedule.scheduled_at = when_utc
        sp = content.schedule
    else:
        sp = ScheduledPost(content_id=content.id, scheduled_at=when_utc)
        db.add(sp)
    content.status = ContentStatus.SCHEDULED
    return sp


@router.post("", response_model=ScheduleOut)
def schedule_one(req: ScheduleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = db.get(ContentItem, req.content_id)
    if not content:
        raise HTTPException(404, "Contenu introuvable")
    get_brand_for_user(content.brand_id, user, db)
    if not content.image_paths:
        raise HTTPException(400, "Ce contenu n'a pas de visuel — fais un rendu d'abord.")
    sp = _attach(content, _to_utc_naive(req.scheduled_at), db)
    db.commit()
    db.refresh(sp)
    return sp


@router.post("/auto", response_model=list[ScheduleOut])
def auto_schedule(req: AutoScheduleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Répartit les contenus prêts (approuvés/brouillons) à raison d'un par jour."""
    get_brand_for_user(req.brand_id, user, db)
    try:
        hh, mm = (int(x) for x in req.time_of_day.split(":"))
        post_time = time(hh, mm)
    except (ValueError, TypeError):
        raise HTTPException(400, "time_of_day invalide (attendu HH:MM)") from None

    candidates = (
        db.query(ContentItem)
        .filter(
            ContentItem.brand_id == req.brand_id,
            ContentItem.status.in_([ContentStatus.APPROVED, ContentStatus.DRAFT]),
        )
        .order_by(ContentItem.created_at.asc())
        .all()
    )
    candidates = [c for c in candidates if c.image_paths]
    if not candidates:
        raise HTTPException(400, "Aucun contenu prêt (avec visuel) à planifier.")

    tz = ZoneInfo(settings.scheduler_timezone)
    base_date = req.start_date.date()
    out: list[ScheduledPost] = []
    for offset in range(min(req.days, len(candidates))):
        day = base_date + timedelta(days=offset)
        local_dt = datetime.combine(day, post_time, tzinfo=tz)
        when_utc = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
        sp = _attach(candidates[offset], when_utc, db)
        db.flush()
        out.append(sp)

    db.commit()
    for sp in out:
        db.refresh(sp)
    return out


@router.get("", response_model=list[ScheduleOut])
def list_schedule(brand_id: Optional[int] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(ScheduledPost).join(ContentItem).join(Brand).filter(Brand.user_id == user.id)
    if brand_id is not None:
        q = q.filter(ContentItem.brand_id == brand_id)
    return q.order_by(ScheduledPost.scheduled_at.asc()).all()


@router.delete("/{schedule_id}")
def unschedule(schedule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sp = db.get(ScheduledPost, schedule_id)
    if not sp:
        raise HTTPException(404, "Créneau introuvable")
    get_brand_for_user(sp.content.brand_id, user, db)
    content = sp.content
    if content and content.status == ContentStatus.SCHEDULED:
        content.status = ContentStatus.APPROVED
    db.delete(sp)
    db.commit()
    return {"ok": True}
