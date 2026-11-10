"""Simple intent router for Alice AI."""

from __future__ import annotations

from pathlib import Path
import unicodedata


DATA_EXTENSIONS = {".csv", ".xlsx"}
TEXT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def route_request(question: str, uploaded_file_name: str | None = None) -> str:
    """Return the module that should handle the request."""
    if uploaded_file_name:
        suffix = Path(uploaded_file_name).suffix.lower()
        if suffix in DATA_EXTENSIONS:
            return "analytics"
        if suffix in TEXT_EXTENSIONS:
            return "temporary_document"

    normalized = normalize_text(question)
    if any(word in normalized for word in ["grafico", "ranking", "kpi", "vendas", "planilha"]):
        return "analytics"
    return "knowledge"
