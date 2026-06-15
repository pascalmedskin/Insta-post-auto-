"""Endpoints produits (pour mockups aux proportions respectées)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Brand, Product
from app.schemas import ProductOut
from app.services.storage import save_upload

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(brand_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Product)
    if brand_id is not None:
        q = q.filter(Product.brand_id == brand_id)
    return q.order_by(Product.created_at.desc()).all()


@router.post("", response_model=ProductOut)
def create_product(
    brand_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    width_mm: float | None = Form(None),
    height_mm: float | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if not db.get(Brand, brand_id):
        raise HTTPException(404, "Marque introuvable")
    product = Product(
        brand_id=brand_id,
        name=name,
        description=description,
        width_mm=width_mm,
        height_mm=height_mm,
        image_path=save_upload(file, prefix="product") if file else None,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    db.delete(product)
    db.commit()
    return {"ok": True}
