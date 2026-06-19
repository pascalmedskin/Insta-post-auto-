"""Endpoints de gestion des marques (identité, logos, guidelines PDF)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.database import get_db
from app.models import Brand
from app.schemas import BrandCreate, BrandOut, BrandUpdate
from app.services.ai_generator import extract_brand_info
from app.services.pdf_import import extract_text
from app.services.storage import save_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.created_at.desc()).all()


@router.post("", response_model=BrandOut)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    brand = Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def _analyze_brand_identity(brand, name, website_url, pdf, db):
    """Analyse PDF uniquement pour l'identité de marque (couleurs, typo, ton)."""
    pdf_text = ""
    if pdf and pdf.filename:
        rel = save_upload(pdf, prefix="guidelines")
        brand.guidelines_pdf_path = rel
        pdf_text = extract_text(MEDIA_DIR / rel.split("/")[-1])

        if pdf_text:
            info = extract_brand_info(pdf_text, name, website_url)
            if info:
                for field in (
                    "primary_color", "secondary_color", "accent_color",
                    "tone_of_voice", "target_audience", "default_hashtags",
                    "font_family", "font_body", "languages", "guidelines",
                ):
                    val = info.get(field)
                    if val:
                        setattr(brand, field, val)
            else:
                brand.guidelines = pdf_text

    if website_url:
        brand.website_url = website_url


@router.post("/setup", response_model=BrandOut)
def setup_brand(
    name: str = Form(...),
    website_url: Optional[str] = Form(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Crée une marque et extrait l'identité visuelle du PDF."""
    brand = Brand(name=name, website_url=website_url or None)
    db.add(brand)
    db.flush()

    _analyze_brand_identity(brand, name, website_url, pdf, db)

    db.commit()
    db.refresh(brand)
    return brand


@router.post("/setup-update/{brand_id}", response_model=BrandOut)
def setup_update_brand(
    brand_id: int,
    name: str = Form(...),
    website_url: Optional[str] = Form(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Ré-analyse un PDF sur une marque existante."""
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")

    _analyze_brand_identity(brand, name, website_url, pdf, db)

    db.commit()
    db.refresh(brand)
    return brand


def _get_brand(brand_id: int, db: Session) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Marque introuvable")
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: int, db: Session = Depends(get_db)):
    return _get_brand(brand_id, db)


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: int, payload: BrandUpdate, db: Session = Depends(get_db)):
    brand = _get_brand(brand_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(brand, key, value)
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/{brand_id}")
def delete_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = _get_brand(brand_id, db)
    db.delete(brand)
    db.commit()
    return {"ok": True}


@router.post("/{brand_id}/logos", response_model=BrandOut)
def upload_logos(
    brand_id: int,
    files: list[UploadFile] = File(...),
    label: str = Form(""),
    variant: str = Form("primary"),
    db: Session = Depends(get_db),
):
    """Ajoute un ou plusieurs logos avec label et variante."""
    brand = _get_brand(brand_id, db)
    logos = list(brand.logos or [])

    for f in files:
        path = save_upload(f, prefix="logo")
        logo_entry = {"path": path, "label": label or f.filename, "variant": variant}
        logos.append(logo_entry)
        if not brand.logo_path:
            brand.logo_path = path

    brand.logos = logos
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/{brand_id}/primary-logo", response_model=BrandOut)
def set_primary_logo(
    brand_id: int, path: str = Form(...), db: Session = Depends(get_db)
):
    brand = _get_brand(brand_id, db)
    all_paths = [
        (l["path"] if isinstance(l, dict) else l)
        for l in (brand.logos or [])
    ]
    if path not in all_paths:
        raise HTTPException(400, "Ce logo n'appartient pas à la marque")
    brand.logo_path = path
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/{brand_id}/logos/{logo_index}", response_model=BrandOut)
def remove_logo(
    brand_id: int, logo_index: int, db: Session = Depends(get_db)
):
    brand = _get_brand(brand_id, db)
    logos = list(brand.logos or [])
    if logo_index < 0 or logo_index >= len(logos):
        raise HTTPException(400, "Index invalide")
    removed = logos.pop(logo_index)
    brand.logos = logos
    removed_path = removed["path"] if isinstance(removed, dict) else removed
    if brand.logo_path == removed_path:
        if logos:
            first = logos[0]
            brand.logo_path = first["path"] if isinstance(first, dict) else first
        else:
            brand.logo_path = None
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/{brand_id}/brand-image", response_model=BrandOut)
def upload_brand_image(
    brand_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    brand = _get_brand(brand_id, db)
    brand.brand_image_path = save_upload(file, prefix="brandimg")
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/{brand_id}/guidelines-pdf", response_model=BrandOut)
def upload_guidelines_pdf(
    brand_id: int,
    file: UploadFile = File(...),
    append: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Importe un PDF de guidelines : on extrait le texte vers `guidelines`."""
    brand = _get_brand(brand_id, db)
    rel = save_upload(file, prefix="guidelines")
    brand.guidelines_pdf_path = rel
    text = extract_text(MEDIA_DIR / rel.split("/")[-1])
    if text:
        brand.guidelines = (
            f"{brand.guidelines}\n\n{text}".strip() if append and brand.guidelines else text
        )
    db.commit()
    db.refresh(brand)
    return brand
