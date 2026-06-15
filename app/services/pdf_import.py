"""Extraction du texte d'un PDF de brand guidelines."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CHARS = 20000  # on borne pour ne pas exploser le contexte de Claude


def extract_text(pdf_path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        logger.warning("pypdf non installé — guidelines PDF ignorées.")
        return ""
    try:
        reader = PdfReader(str(pdf_path))
        chunks = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(chunks).strip()
        return text[:MAX_CHARS]
    except Exception:  # pragma: no cover
        logger.exception("Échec extraction PDF.")
        return ""
