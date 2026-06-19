"""Endpoints produits (pour mockups aux proportions respectées)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import logging

from app.database import get_db
from app.models import Brand, Product
from app.schemas import ProductOut
from app.services.ai_generator import extract_single_product
from app.services.storage import save_upload
from app.services.web_scraper import fetch_page_text, scrape_all_product_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(brand_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Product)
    if brand_id is not None:
        q = q.filter(Product.brand_id == brand_id)
    return q.order_by(Product.created_at.desc()).all()


@router.post("", response_model=ProductOut)
def create_product(
    brand_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    width_mm: Optional[float] = Form(None),
    height_mm: Optional[float] = Form(None),
    depth_mm: Optional[float] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if not db.get(Brand, brand_id):
        raise HTTPException(404, "Marque introuvable")
    img = save_upload(file, prefix="product") if file and file.filename else None
    product = Product(
        brand_id=brand_id,
        name=name,
        description=description,
        width_mm=width_mm,
        height_mm=height_mm,
        depth_mm=depth_mm,
        image_path=img,
        images=[{"path": img, "label": "Principal"}] if img else [],
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    width_mm: Optional[float] = Form(None),
    height_mm: Optional[float] = Form(None),
    depth_mm: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    if name is not None:
        product.name = name
    if description is not None:
        product.description = description
    if width_mm is not None:
        product.width_mm = width_mm
    if height_mm is not None:
        product.height_mm = height_mm
    if depth_mm is not None:
        product.depth_mm = depth_mm
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/images", response_model=ProductOut)
def upload_product_images(
    product_id: int,
    label: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Ajoute une ou plusieurs photos/vues au produit."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    images = list(product.images or [])
    labels = ["Face", "Profil", "Dos", "Dessus", "Dessous", "Détail", "En situation"]
    for i, f in enumerate(files):
        path = save_upload(f, prefix="product")
        lbl = label if label else (labels[len(images) + i] if (len(images) + i) < len(labels) else f"Vue {len(images) + i + 1}")
        images.append({"path": path, "label": lbl})
        if not product.image_path:
            product.image_path = path
    product.images = images
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/primary-image", response_model=ProductOut)
def set_primary_image(
    product_id: int,
    path: str = Form(...),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    if not any(img["path"] == path for img in (product.images or [])):
        raise HTTPException(400, "Cette image n'appartient pas au produit")
    product.image_path = path
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}/images/{image_index}", response_model=ProductOut)
def remove_product_image(
    product_id: int,
    image_index: int,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    images = list(product.images or [])
    if image_index < 0 or image_index >= len(images):
        raise HTTPException(400, "Index invalide")
    removed = images.pop(image_index)
    product.images = images
    if product.image_path == removed["path"]:
        product.image_path = images[0]["path"] if images else None
    db.commit()
    db.refresh(product)
    return product


@router.post("/from-url", response_model=ProductOut)
def create_product_from_url(
    brand_id: int = Form(...),
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Analyse une page produit : extrait nom, description, dimensions + images."""
    if not db.get(Brand, brand_id):
        raise HTTPException(404, "Marque introuvable")
    page_text = fetch_page_text(url)
    if not page_text:
        raise HTTPException(400, "Impossible de charger cette page")
    brand = db.get(Brand, brand_id)
    langs = brand.languages or ["fr"]
    info = extract_single_product(page_text, brand.name, languages=langs)
    downloaded = scrape_all_product_images(url)
    labels = ["Face", "Profil", "Dos", "Dessus", "Détail", "En situation"]
    images = []
    for i, path in enumerate(downloaded):
        lbl = labels[i] if i < len(labels) else f"Vue {i + 1}"
        images.append({"path": path, "label": lbl})
    product = Product(
        brand_id=brand_id,
        name=info.get("name", "Produit sans nom"),
        description=info.get("description", ""),
        descriptions=info.get("descriptions", {}),
        product_url=url,
        width_mm=info.get("width_mm"),
        height_mm=info.get("height_mm"),
        depth_mm=info.get("depth_mm"),
        image_path=images[0]["path"] if images else None,
        images=images,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    logger.info("Produit créé depuis URL: %s (%d images)", product.name, len(images))
    return product


@router.post("/{product_id}/import-images", response_model=ProductOut)
def import_images_from_url(
    product_id: int,
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Scrape la page produit et importe toutes les images trouvées."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produit introuvable")
    product.product_url = url
    downloaded = scrape_all_product_images(url)
    if not downloaded:
        db.commit()
        raise HTTPException(400, "Aucune image trouvée sur cette page")
    images = list(product.images or [])
    labels = ["Face", "Profil", "Dos", "Dessus", "Détail", "En situation"]
    for i, path in enumerate(downloaded):
        lbl = labels[len(images) + i] if (len(images) + i) < len(labels) else f"Vue {len(images) + i + 1}"
        images.append({"path": path, "label": lbl})
        if not product.image_path:
            product.image_path = path
    product.images = images
    logger.info("Importé %d images depuis %s pour produit %s", len(downloaded), url, product.name)
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
