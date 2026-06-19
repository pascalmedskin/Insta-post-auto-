"""Point d'entrée FastAPI : API + UI statique + scheduler auto-post."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import brands, content, instagram, products, schedule
from app.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Insta Post Auto", version="0.1.0", lifespan=lifespan)

app.include_router(brands.router)
app.include_router(products.router)
app.include_router(content.router)
app.include_router(schedule.router)
app.include_router(instagram.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "text_ai": settings.has_text_ai,
        "image_ai": settings.has_image_ai,
        "instagram": settings.has_instagram,
        "meta_oauth": settings.has_meta_oauth,
        "autopost": settings.autopost_enabled,
    }


@app.get("/")
def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
