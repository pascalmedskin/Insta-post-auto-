"""Endpoints de planification : créneau manuel + auto-remplissage quotidien."""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_brand_for_user
from app.models import ContentItem, ContentFormat, ContentStatus, ScheduledPost, Brand, User
from app.schemas import AutoScheduleRequest, ScheduleOut, ScheduleRequest, SmartScheduleRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _to_utc_naive(dt: datetime) -> datetime:
    """Normalise un datetime (aware ou non) en UTC naïf pour la comparaison."""
    if dt.tzinfo is None:
        # Supposé exprimé dans le fuseau du scheduler.
        dt = dt.replace(tzinfo=ZoneInfo(settings.scheduler_timezone))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _attach(content: ContentItem, when_utc: datetime, db: Session, publish_mode: str = "auto") -> ScheduledPost:
    if content.schedule:
        content.schedule.scheduled_at = when_utc
        content.schedule.publish_mode = publish_mode
        sp = content.schedule
    else:
        sp = ScheduledPost(content_id=content.id, scheduled_at=when_utc, publish_mode=publish_mode)
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
    sp = _attach(content, _to_utc_naive(req.scheduled_at), db, publish_mode=req.publish_mode)
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


# ── AI Smart Scheduler ──────────────────────────────────────────────

_SMART_SYSTEM = (
    "Tu es un assistant de planification Instagram. L'utilisateur décrit en langage "
    "naturel comment il veut planifier ses publications. Tu dois traduire cette "
    "instruction en créneaux structurés.\n\n"
    "Réponds UNIQUEMENT en JSON valide, sans texte autour.\n\n"
    "Format attendu :\n"
    '{"slots": [\n'
    '  {"format": "story", "time": "12:00", "days": [1,2,3,4,5]},\n'
    '  {"format": "post", "time": "08:00", "days": [1,2,3,4,5]},\n'
    '  {"format": "carousel", "time": "20:00", "days": [1,2,3,4,5]}\n'
    "]}\n\n"
    "Règles :\n"
    "- format : 'post', 'story' ou 'carousel'\n"
    "- time : heure locale HH:MM (24h)\n"
    "- days : jours de la semaine (1=lundi … 7=dimanche)\n"
    "- Si l'utilisateur dit 'tous les jours' → [1,2,3,4,5,6,7]\n"
    "- Si 'en semaine' ou 'jours ouvrés' → [1,2,3,4,5]\n"
    "- Si 'weekends' → [6,7]\n"
    "- Si l'utilisateur ne précise pas le format, utilise 'post'\n"
    "- Si l'utilisateur ne précise pas les jours, utilise [1,2,3,4,5,6,7]\n"
    "- Si l'utilisateur ne précise pas l'heure, utilise '09:00'\n"
)


def _parse_instruction(instruction: str) -> list[dict]:
    """Use Claude to parse a natural language scheduling instruction."""
    if not settings.has_text_ai:
        raise HTTPException(400, "ANTHROPIC_API_KEY non configurée — l'IA n'est pas disponible.")

    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.text_model,
        max_tokens=1000,
        system=_SMART_SYSTEM,
        messages=[{"role": "user", "content": instruction}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()

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

    try:
        data = json.loads(raw)
        return data.get("slots", [])
    except (json.JSONDecodeError, AttributeError):
        logger.error("AI schedule parse failed: %s", raw[:500])
        raise HTTPException(400, "Impossible de comprendre l'instruction. Reformule ta demande.") from None


@router.post("/smart")
def smart_schedule(req: SmartScheduleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI-powered scheduler: parse natural language instruction, distribute library content."""
    brand = get_brand_for_user(req.brand_id, user, db)

    slots = _parse_instruction(req.instruction)
    if not slots:
        raise HTTPException(400, "Aucun créneau détecté dans l'instruction.")

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
        raise HTTPException(400, "Aucun contenu prêt (avec visuel) dans la bibliothèque.")

    by_format: dict[str, list[ContentItem]] = {"post": [], "story": [], "carousel": []}
    for c in candidates:
        fmt = c.format.value if isinstance(c.format, ContentFormat) else c.format
        if fmt in by_format:
            by_format[fmt].append(c)

    tz = ZoneInfo(settings.scheduler_timezone)
    today = date.today()
    tomorrow = today + timedelta(days=1)

    scheduled: list[dict] = []
    used_ids: set[int] = set()

    for week_offset in range(13):
        if not any(by_format.values()):
            break

        for slot in slots:
            fmt = slot.get("format", "post")
            time_str = slot.get("time", "09:00")
            days = slot.get("days", [1, 2, 3, 4, 5, 6, 7])

            try:
                hh, mm = int(time_str.split(":")[0]), int(time_str.split(":")[1])
                slot_time = time(hh, mm)
            except (ValueError, IndexError):
                slot_time = time(9, 0)

            for day_num in days:
                days_ahead = (day_num - tomorrow.isoweekday()) % 7 + (week_offset * 7)
                target_date = tomorrow + timedelta(days=days_ahead)

                if target_date <= today:
                    continue

                pool = by_format.get(fmt, [])
                if not pool:
                    for fallback_fmt in ["post", "story", "carousel"]:
                        if fallback_fmt != fmt and by_format.get(fallback_fmt):
                            pool = by_format[fallback_fmt]
                            fmt = fallback_fmt
                            break
                if not pool:
                    continue

                content = pool.pop(0)
                used_ids.add(content.id)

                local_dt = datetime.combine(target_date, slot_time, tzinfo=tz)
                when_utc = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
                sp = _attach(content, when_utc, db)
                db.flush()

                scheduled.append({
                    "content_id": content.id,
                    "format": content.format.value if isinstance(content.format, ContentFormat) else content.format,
                    "date": target_date.isoformat(),
                    "time": time_str,
                })

        if not any(by_format.values()):
            break

    db.commit()

    slot_desc = ", ".join(
        f"{s.get('format', 'post')} à {s.get('time', '09:00')}"
        for s in slots
    )

    return {
        "ok": True,
        "scheduled_count": len(scheduled),
        "slots_parsed": slots,
        "summary": f"{len(scheduled)} publications programmées ({slot_desc})",
        "details": scheduled,
    }
