"""Modèles ORM : marque, contenus générés, publications planifiées."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentFormat(str, enum.Enum):
    POST = "post"          # post simple (1 image)
    CAROUSEL = "carousel"  # plusieurs slides
    STORY = "story"        # story verticale


class ContentStatus(str, enum.Enum):
    DRAFT = "draft"          # généré, en attente de validation
    APPROVED = "approved"    # validé, prêt à être planifié
    SCHEDULED = "scheduled"  # rattaché à un créneau
    PUBLISHED = "published"  # publié sur Instagram
    FAILED = "failed"        # échec de publication


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fb_user_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), default="")
    picture_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    brands: Mapped[List["Brand"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    user: Mapped["User"] = relationship()


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Identité visuelle
    logo_path: Mapped[Optional[str]] = mapped_column(String(500))
    logos: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    brand_image_path: Mapped[Optional[str]] = mapped_column(String(500))
    guidelines_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    primary_color: Mapped[str] = mapped_column(String(20), default="#111111")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#FFFFFF")
    accent_color: Mapped[str] = mapped_column(String(20), default="#FF4D6D")
    font_family: Mapped[str] = mapped_column(String(120), default="DejaVu Sans")
    font_body: Mapped[str] = mapped_column(String(120), default="")
    # Charte / ligne éditoriale
    languages: Mapped[Optional[list]] = mapped_column(JSON, default=lambda: ["fr"])
    website_url: Mapped[Optional[str]] = mapped_column(String(500))
    products_url: Mapped[Optional[str]] = mapped_column(String(500))
    guidelines: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(String(300), default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="")
    default_hashtags: Mapped[str] = mapped_column(Text, default="")

    # Instagram connection (per-brand, via OAuth)
    ig_access_token: Mapped[Optional[str]] = mapped_column(String(500), default="")
    ig_user_id: Mapped[Optional[str]] = mapped_column(String(120), default="")
    ig_username: Mapped[Optional[str]] = mapped_column(String(120), default="")

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    contents: Mapped[List[ContentItem]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    products: Mapped[List[Product]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    user: Mapped[Optional["User"]] = relationship(back_populates="brands")


class Product(Base):
    """Produit d'une marque, avec dimensions réelles pour des mockups
    aux proportions respectées."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    descriptions: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    product_url: Mapped[Optional[str]] = mapped_column(String(500))
    image_path: Mapped[Optional[str]] = mapped_column(String(500))
    images: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    width_mm: Mapped[Optional[float]] = mapped_column()
    height_mm: Mapped[Optional[float]] = mapped_column()
    depth_mm: Mapped[Optional[float]] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped[Brand] = relationship(back_populates="products")


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    # Produit optionnel à mettre en scène (mockup).
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    format: Mapped[ContentFormat] = mapped_column(
        Enum(ContentFormat), default=ContentFormat.POST
    )
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus), default=ContentStatus.DRAFT
    )

    # Brief / angle
    prompt: Mapped[str] = mapped_column(Text, default="")
    angle: Mapped[str] = mapped_column(String(120), default="")  # angle d'attaque

    # Copy
    hook: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    # Pour carousels/stories : liste de slides [{"headline":..., "body":...}]
    slides: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Visuels : chemins relatifs dans static/media (1+ images)
    image_paths: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    ig_media_id: Mapped[Optional[str]] = mapped_column(String(120))
    error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped[Brand] = relationship(back_populates="contents")
    product: Mapped[Optional[Product]] = relationship()
    schedule: Mapped[Optional[ScheduledPost]] = relationship(
        back_populates="content", cascade="all, delete-orphan", uselist=False
    )


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id"), nullable=False, unique=True
    )
    # Heure de publication (UTC stocké, affiché dans le tz du scheduler)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    content: Mapped[ContentItem] = relationship(back_populates="schedule")
