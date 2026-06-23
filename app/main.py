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
from app.routers import auth, brands, content, instagram, products, push, schedule
from app.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Magic Post", version="0.2.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(brands.router)
app.include_router(products.router)
app.include_router(content.router)
app.include_router(schedule.router)
app.include_router(push.router)
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


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/")
def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
