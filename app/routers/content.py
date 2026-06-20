"""Endpoints de génération et gestion des contenus."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_brand_for_user
from app.models import Brand, ContentItem, ContentStatus, Product, User
from app.schemas import ContentOut, ContentUpdate, GenerateRequest, RenderRequest
from app.services import ai_generator, composer
from app.services.instagram import InstagramError, publish_content

router = APIRouter(prefix="/api/content", tags=["content"])


@router.post("/generate", response_model=list[ContentOut])
def generate(req: GenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    brand = get_brand_for_user(req.brand_id, user, db)

    product = None
    if req.product_id:
        product = db.get(Product, req.product_id)
        if not product or product.brand_id != brand.id:
            raise HTTPException(400, "Produit invalide pour cette marque")

    variations = ai_generator.generate_variations(
        brand, req.prompt, req.format, req.variations, language=req.language
    )

    created: list[ContentItem] = []
    for v in variations:
        item = ContentItem(
            brand_id=brand.id,
            product_id=product.id if product else None,
            format=req.format,
            status=ContentStatus.DRAFT,
            prompt=req.prompt,
            angle=v.get("angle", ""),
            hook=v.get("hook", ""),
            caption=v.get("caption", ""),
            hashtags=v.get("hashtags", ""),
            slides=v.get("slides", []),
        )
        db.add(item)
        db.flush()  # pour avoir l'id et la relation produit
        item.product = product
        item.image_paths = []
        # Étape 1 par défaut = hooks seuls. La composition (et l'image IA) se
        # fait à l'étape suivante via /render, à partir du hook choisi.
        if req.auto_compose:
            try:
                item.image_paths = composer.compose_content(
                    brand, item, use_ai_image=req.generate_images
                )
            except Exception as exc:  # noqa: BLE001
                item.error = f"Composition visuelle échouée: {exc}"
                item.image_paths = []
        created.append(item)

    db.commit()
    for item in created:
        db.refresh(item)
    return created


@router.get("", response_model=list[ContentOut])
def list_content(
    brand_id: Optional[int] = None,
    status: Optional[ContentStatus] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ContentItem).join(Brand).filter(Brand.user_id == user.id)
    if brand_id is not None:
        q = q.filter(ContentItem.brand_id == brand_id)
    if status is not None:
        q = q.filter(ContentItem.status == status)
    return q.order_by(ContentItem.created_at.desc()).all()


def _get(content_id: int, user: User, db: Session) -> ContentItem:
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(404, "Contenu introuvable")
    get_brand_for_user(item.brand_id, user, db)
    return item


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get(content_id, user, db)


@router.patch("/{content_id}", response_model=ContentOut)
def update_content(
    content_id: int, payload: ContentUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = _get(content_id, user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{content_id}/render", response_model=ContentOut)
def render_content(
    content_id: int,
    req: RenderRequest = RenderRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Génère l'image à partir du hook (étape 2). `use_ai_image` choisit
    une image IA ou l'image de marque comme fond."""
    item = _get(content_id, user, db)
    try:
        item.image_paths = composer.compose_content(
            item.brand, item, use_ai_image=req.use_ai_image,
            quality=req.quality,
        )
        item.error = None
    except Exception as exc:  # noqa: BLE001
        item.error = f"Composition visuelle échouée: {exc}"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{content_id}/publish", response_model=ContentOut)
def publish_now(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get(content_id, user, db)
    try:
        item.ig_media_id = publish_content(item)
        item.status = ContentStatus.PUBLISHED
        item.error = None
    except InstagramError as exc:
        item.status = ContentStatus.FAILED
        item.error = str(exc)
        db.commit()
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{content_id}")
def delete_content(content_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get(content_id, user, db)
    db.delete(item)
    db.commit()
    return {"ok": True}
