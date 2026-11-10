"""Persistent vector store for corporate knowledge supporting Ollama and Gemini."""

from __future__ import annotations

try:
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

from pathlib import Path
from typing import Any

import chromadb

from src.config.settings import settings
from src.providers.embedding_provider import (
    GeminiEmbeddingFunction,
    OllamaEmbeddingFunction,
    get_embedding_function,
)
from src.utils.file_readers import read_document


COLLECTION_NAME = "daniel_base_corporativa"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
SUPPORTED_DOC_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}


def _get_client():
    settings.chroma_db_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_db_path))


def _get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


def add_document(file_path: str | Path, sector: str, classification: str = "publica") -> int:
    if classification.lower().strip() == "confidencial":
        raise ValueError("Documentos confidenciais não podem ser adicionados à base vetorial.")

    file_path = Path(file_path)
    text = read_document(file_path)
    chunks = chunk_text(text)
    if not chunks:
        return 0

    collection = _get_collection()
    ids = [f"{sector}_{file_path.stem}_{index}" for index in range(len(chunks))]
    metadatas = [
        {
            "fonte": file_path.name,
            "setor": sector,
            "classificacao": classification,
        }
        for _ in chunks
    ]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def add_documents_from_folder(folder_path: str | Path | None = None) -> dict[str, int]:
    root = Path(folder_path or settings.company_docs_path)
    result = {}
    if not root.exists():
        return result

    for sector_dir in sorted(root.iterdir()):
        if not sector_dir.is_dir():
            continue
        for file_path in sorted(sector_dir.iterdir()):
            if file_path.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
                result[file_path.name] = add_document(file_path, sector=sector_dir.name)
    return result


def query(question: str, n_results: int | None = None, sector_filter: str | None = None) -> list[dict]:
    collection = _get_collection()
    query_params: dict[str, Any] = {
        "query_texts": [question],
        "n_results": n_results or settings.rag_n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if sector_filter and sector_filter.strip():
        clean_s = sector_filter.lower().strip()
        if not clean_s.startswith("todos"):
            query_params["where"] = {"setor": clean_s}

    result = collection.query(**query_params)

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    passages = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        passages.append(
            {
                "texto": text,
                "fonte": metadata.get("fonte", "desconhecida"),
                "setor": metadata.get("setor", "desconhecido"),
                "classificacao": metadata.get("classificacao", "desconhecida"),
                "distancia": distance,
            }
        )
    return passages


def has_relevant_context(passages: list[dict]) -> bool:
    if not passages:
        return False
    best_distance = min(item.get("distancia", 999) for item in passages)
    return best_distance <= settings.rag_max_distance


def rebuild_base() -> dict[str, int]:
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return add_documents_from_folder()


def get_vector_store_stats() -> dict[str, Any]:
    """Return stats about the vector database and corporate documents."""
    collection = _get_collection()
    total_chunks = collection.count()

    sector_counts: dict[str, int] = {}
    if total_chunks > 0:
        get_res = collection.get(include=["metadatas"])
        metadatas = get_res.get("metadatas") or []
        for meta in metadatas:
            setor = meta.get("setor", "outros").lower()
            sector_counts[setor] = sector_counts.get(setor, 0) + 1

    db_path = settings.chroma_db_path
    size_bytes = 0
    if db_path.exists():
        size_bytes = sum(f.stat().st_size for f in db_path.glob("**/*") if f.is_file())

    return {
        "total_chunks": total_chunks,
        "sector_counts": sector_counts,
        "db_size_mb": round(size_bytes / (1024 * 1024), 2),
    }


def ensure_vector_store_populated() -> int:
    """Check if vector store is empty. If empty, populate from company_docs folder."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            added = add_documents_from_folder()
            return sum(added.values())
    except Exception as exc:
        print(f"[VectorStore] Aviso ao verificar/indexar base: {exc}")
    return 0
