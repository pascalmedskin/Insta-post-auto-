"""Auto-post : worker APScheduler qui publie les contenus arrivés à échéance.

Tourne dans le process FastAPI. Toutes les minutes, il cherche les
ScheduledPost dont l'heure est passée et dont le contenu n'est pas encore
publié, puis tente la publication via l'API Graph.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.models import ContentStatus, ScheduledPost
from app.services.instagram import publish_content

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
_scheduler: BackgroundScheduler | None = None


def _process_due_posts() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        due = (
            db.query(ScheduledPost)
            .filter(
                ScheduledPost.published_at.is_(None),
                ScheduledPost.scheduled_at <= now,
                ScheduledPost.attempts < MAX_ATTEMPTS,
            )
            .all()
        )
        for sp in due:
            content = sp.content
            if not content or content.status == ContentStatus.PUBLISHED:
                continue
            sp.attempts += 1
            try:
                media_id = publish_content(content)
                content.ig_media_id = media_id
                content.status = ContentStatus.PUBLISHED
                content.error = None
                sp.published_at = now
                logger.info("Publié contenu #%s (media %s)", content.id, media_id)
            except Exception as exc:  # noqa: BLE001
                content.error = str(exc)
                if sp.attempts >= MAX_ATTEMPTS:
                    content.status = ContentStatus.FAILED
                logger.exception("Échec publication contenu #%s", content.id)
            db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not settings.autopost_enabled:
        logger.info("Auto-post désactivé (AUTOPOST_ENABLED=false).")
        return
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(
        _process_due_posts,
        "interval",
        minutes=1,
        id="autopost",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler auto-post démarré (tz=%s).", settings.scheduler_timezone)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
