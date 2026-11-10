"""Central configuration and identity definitions for Alice AI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

ASSISTANT_NAME = "Alice"
ASSISTANT_TITLE = "Alice AI"
ASSISTANT_ROLE_SUMMARY = (
    "Assistente virtual informativa que consulta documentos corporativos para "
    "explicar regras, requisitos e procedimentos."
)
INSTITUTIONAL_CREDIT = (
    "Desenvolvido pelo Polo Inova do IFAM CMDI, com participação dos alunos do AX Academy."
)
COMPANY_NAME = "DNEL SOM Serviços Inteligentes"


@dataclass(frozen=True)
class Settings:
    # Identity & Institutional Presentation
    assistant_name: str = os.getenv("ASSISTANT_NAME", ASSISTANT_NAME)
    assistant_title: str = os.getenv("ASSISTANT_TITLE", ASSISTANT_TITLE)
    assistant_role_summary: str = ASSISTANT_ROLE_SUMMARY
    institutional_credit: str = INSTITUTIONAL_CREDIT
    company_name: str = COMPANY_NAME

    # Provider: 'ollama' (default, local) or 'gemini' (cloud)
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    # Ollama Local Settings
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:3b")
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "90"))

    # Gemini Cloud Settings (optional, only used if LLM_PROVIDER=gemini)
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    chat_model: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
    embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")

    # Admin Credentials
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "Daniel@2026")

    # Storage Paths
    chroma_db_path: Path = Path(os.getenv("CHROMA_DB_PATH", PROJECT_ROOT / "chroma_db"))
    company_docs_path: Path = Path(os.getenv("COMPANY_DOCS_PATH", PROJECT_ROOT / "company_docs"))
    temp_uploads_path: Path = Path(os.getenv("TEMP_UPLOADS_PATH", PROJECT_ROOT / "uploads_temp"))
    exports_path: Path = Path(os.getenv("EXPORTS_PATH", PROJECT_ROOT / "exports"))

    # RAG Search Tuning
    rag_n_results: int = int(os.getenv("RAG_N_RESULTS", "4"))
    rag_max_distance: float = float(os.getenv("RAG_MAX_DISTANCE", "0.60"))


settings = Settings()
