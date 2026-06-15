"""Modèles ORM : marque, contenus générés, publications planifiées."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

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


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Identité visuelle
    logo_path: Mapped[str | None] = mapped_column(String(500))  # logo principal
    logos: Mapped[list | None] = mapped_column(JSON, default=list)  # tous les logos PNG
    brand_image_path: Mapped[str | None] = mapped_column(String(500))
    guidelines_pdf_path: Mapped[str | None] = mapped_column(String(500))
    primary_color: Mapped[str] = mapped_column(String(20), default="#111111")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#FFFFFF")
    accent_color: Mapped[str] = mapped_column(String(20), default="#FF4D6D")
    font_family: Mapped[str] = mapped_column(String(120), default="DejaVu Sans")
    # Charte / ligne éditoriale
    guidelines: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(String(300), default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="")
    default_hashtags: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    contents: Mapped[list[ContentItem]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    products: Mapped[list[Product]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )


class Product(Base):
    """Produit d'une marque, avec dimensions réelles pour des mockups
    aux proportions respectées."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(500))
    # Dimensions réelles, en millimètres (pour respecter le ratio L/H).
    width_mm: Mapped[float | None] = mapped_column()
    height_mm: Mapped[float | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped[Brand] = relationship(back_populates="products")


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    # Produit optionnel à mettre en scène (mockup).
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))

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
    slides: Mapped[list | None] = mapped_column(JSON, default=list)

    # Visuels : chemins relatifs dans static/media (1+ images)
    image_paths: Mapped[list | None] = mapped_column(JSON, default=list)

    ig_media_id: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped[Brand] = relationship(back_populates="contents")
    product: Mapped[Product | None] = relationship()
    schedule: Mapped[ScheduledPost | None] = relationship(
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
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    content: Mapped[ContentItem] = relationship(back_populates="schedule")
