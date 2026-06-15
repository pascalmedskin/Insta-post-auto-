"""Schémas Pydantic pour l'API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ContentFormat, ContentStatus


# --- Brand -----------------------------------------------------------------
class BrandBase(BaseModel):
    name: str
    primary_color: str = "#111111"
    secondary_color: str = "#FFFFFF"
    accent_color: str = "#FF4D6D"
    font_family: str = "DejaVu Sans"
    guidelines: str = ""
    tone_of_voice: str = ""
    target_audience: str = ""
    default_hashtags: str = ""


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BrandBase):
    name: str | None = None


class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    logo_path: str | None = None
    logos: list | None = None
    brand_image_path: str | None = None
    guidelines_pdf_path: str | None = None
    created_at: datetime


# --- Product ---------------------------------------------------------------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand_id: int
    name: str
    description: str
    image_path: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    created_at: datetime


# --- Génération ------------------------------------------------------------
class GenerateRequest(BaseModel):
    brand_id: int
    prompt: str = Field(..., description="Sujet / brief du contenu à décliner")
    format: ContentFormat = ContentFormat.POST
    variations: int = Field(10, ge=1, le=30)
    product_id: int | None = Field(
        None, description="Produit à mettre en scène (mockup), optionnel"
    )
    # Étape 1 = hooks seuls (rapide) ; on génère l'image ensuite via /render.
    auto_compose: bool = Field(
        False, description="Composer les visuels immédiatement (sinon hooks seuls)"
    )
    generate_images: bool = Field(
        True, description="Utiliser l'IA d'images lors de la composition"
    )


class RenderRequest(BaseModel):
    use_ai_image: bool = Field(
        True, description="Générer une image IA comme fond (sinon image de marque)"
    )


class SlideOut(BaseModel):
    headline: str = ""
    body: str = ""


class ContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand_id: int
    product_id: int | None = None
    format: ContentFormat
    status: ContentStatus
    prompt: str
    angle: str
    hook: str
    caption: str
    hashtags: str
    slides: list | None = None
    image_paths: list | None = None
    ig_media_id: str | None = None
    error: str | None = None
    created_at: datetime


class ContentUpdate(BaseModel):
    hook: str | None = None
    caption: str | None = None
    hashtags: str | None = None
    slides: list | None = None
    status: ContentStatus | None = None


# --- Scheduling ------------------------------------------------------------
class ScheduleRequest(BaseModel):
    content_id: int
    scheduled_at: datetime = Field(..., description="Date/heure (ISO 8601)")


class AutoScheduleRequest(BaseModel):
    brand_id: int
    start_date: datetime
    time_of_day: str = Field("09:00", description="HH:MM, heure locale du scheduler")
    days: int = Field(7, ge=1, le=90, description="Nombre de jours à remplir")


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    content_id: int
    scheduled_at: datetime
    published_at: datetime | None = None
    attempts: int
