"""Endpoints de gestion des marques (identité, logos, guidelines PDF)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.database import get_db
from app.models import Brand
from app.schemas import BrandCreate, BrandOut, BrandUpdate
from app.services.pdf_import import extract_text
from app.services.storage import save_upload

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
    db: Session = Depends(get_db),
):
    """Ajoute un ou plusieurs logos PNG (individuellement)."""
    brand = _get_brand(brand_id, db)
    logos = list(brand.logos or [])
    for f in files:
        logos.append(save_upload(f, prefix="logo"))
    brand.logos = logos
    if not brand.logo_path and logos:
        brand.logo_path = logos[0]
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/{brand_id}/primary-logo", response_model=BrandOut)
def set_primary_logo(
    brand_id: int, path: str = Form(...), db: Session = Depends(get_db)
):
    brand = _get_brand(brand_id, db)
    if path not in (brand.logos or []):
        raise HTTPException(400, "Ce logo n'appartient pas à la marque")
    brand.logo_path = path
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
