"""Schémas Pydantic pour l'API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ContentFormat, ContentStatus


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    picture_url: Optional[str] = None


# --- Brand -----------------------------------------------------------------
class BrandBase(BaseModel):
    name: str
    primary_color: str = "#111111"
    secondary_color: str = "#FFFFFF"
    accent_color: str = "#FF4D6D"
    font_family: str = "DejaVu Sans"
    font_body: str = ""
    languages: Optional[list] = None
    website_url: Optional[str] = None
    products_url: Optional[str] = None
    guidelines: str = ""
    tone_of_voice: str = ""
    target_audience: str = ""
    default_hashtags: str = ""


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BrandBase):
    name: Optional[str] = None


class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    website_url: Optional[str] = None
    products_url: Optional[str] = None
    logo_path: Optional[str] = None
    logos: Optional[list] = None
    brand_image_path: Optional[str] = None
    guidelines_pdf_path: Optional[str] = None
    ig_user_id: Optional[str] = None
    ig_username: Optional[str] = None
    created_at: datetime


# --- Product ---------------------------------------------------------------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand_id: int
    name: str
    description: str
    descriptions: Optional[dict] = None
    product_url: Optional[str] = None
    image_path: Optional[str] = None
    images: Optional[list] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    created_at: datetime


# --- Génération ------------------------------------------------------------
class GenerateRequest(BaseModel):
    brand_id: int
    prompt: str = Field(..., description="Sujet / brief du contenu à décliner")
    format: ContentFormat = ContentFormat.POST
    variations: int = Field(10, ge=1, le=30)
    language: str = Field("fr", description="Langue de génération (code ISO)")
    product_id: Optional[int] = Field(
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
    quality: str = Field(
        "draft", description="'draft' = rapide/moins cher, 'hd' = haute qualité"
    )


class SlideOut(BaseModel):
    headline: str = ""
    body: str = ""


class ContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand_id: int
    product_id: Optional[int] = None
    format: ContentFormat
    status: ContentStatus
    prompt: str
    angle: str
    hook: str
    caption: str
    hashtags: str
    slides: Optional[list] = None
    image_paths: Optional[list] = None
    ig_media_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


class ContentUpdate(BaseModel):
    hook: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    slides: Optional[list] = None
    status: Optional[ContentStatus] = None


# --- Scheduling ------------------------------------------------------------
class ScheduleRequest(BaseModel):
    content_id: int
    scheduled_at: datetime = Field(..., description="Date/heure (ISO 8601)")


class AutoScheduleRequest(BaseModel):
    brand_id: int
    start_date: datetime
    time_of_day: str = Field("09:00", description="HH:MM, heure locale du scheduler")
    days: int = Field(7, ge=1, le=90, description="Nombre de jours à remplir")


class SmartScheduleRequest(BaseModel):
    brand_id: int
    instruction: str = Field(..., description="Instruction en langage naturel pour le planning")


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    content_id: int
    scheduled_at: datetime
    published_at: Optional[datetime] = None
    attempts: int
