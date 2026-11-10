"""Embedding providers for ChromaDB supporting Ollama (local) and Gemini (cloud)."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from typing import List

from chromadb import Documents, EmbeddingFunction, Embeddings

from src.config.settings import settings
from src.core.errors import extract_retry_seconds, is_quota_error


def _l2_normalize(vec: list[float]) -> list[float]:
    """Normalize vector to unit length (L2 norm = 1.0)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Embedding function using local Ollama model (e.g. nomic-embed-text) with L2 normalization."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_embedding_model
        self.timeout = timeout

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: List[List[float]] = []
        url = f"{self.base_url}/api/embeddings"

        for text in input:
            payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    emb = data.get("embedding")
                    if not emb:
                        raise ValueError(f"Ollama não retornou vetor para o modelo {self.model}.")
                    embeddings.append(_l2_normalize(emb))
            except urllib.error.URLError as exc:
                reason = str(exc.reason).lower()
                if "connection refused" in reason or "conexão recusada" in reason:
                    raise ConnectionError(
                        f"Ollama indisponível em {self.base_url}. Inicie o Ollama com 'ollama serve'."
                    ) from exc
                raise
            except urllib.error.HTTPError as exc:
                err_text = exc.read().decode("utf-8", errors="replace")
                if exc.code == 404 or "not found" in err_text.lower():
                    raise FileNotFoundError(
                        f"Modelo de embedding '{self.model}' não encontrado. Baixe com 'ollama pull {self.model}'."
                    ) from exc
                raise

        return embeddings

    @staticmethod
    def name() -> str:
        return "ollama_embedding_function"


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Embedding function using Google Gemini API."""

    def __init__(self, api_key: str | None = None, task_type: str = "retrieval_document"):
        self.api_key = api_key or settings.google_api_key
        if not self.api_key:
            raise EnvironmentError("GOOGLE_API_KEY não configurada no .env.")

        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        self.task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        import google.generativeai as genai

        embeddings = []
        for text in input:
            for attempt in range(5):
                try:
                    result = genai.embed_content(
                        model=settings.embedding_model,
                        content=text,
                        task_type=self.task_type,
                    )
                    embeddings.append(result["embedding"])
                    break
                except Exception as exc:
                    if is_quota_error(exc) and attempt < 4:
                        wait_sec = extract_retry_seconds(exc) or (2 ** attempt * 5)
                        time.sleep(min(wait_sec + 2, 35))
                    else:
                        raise
        return embeddings

    @staticmethod
    def name() -> str:
        return "gemini_embedding_function"


def get_embedding_function() -> EmbeddingFunction:
    """Return embedding function according to configured LLM_PROVIDER."""
    provider = (settings.llm_provider or "ollama").lower().strip()
    if provider == "gemini":
        return GeminiEmbeddingFunction()
    return OllamaEmbeddingFunction()
