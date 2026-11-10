"""User-facing error handling helpers for both Ollama (local) and Gemini (cloud)."""

from __future__ import annotations

import re


def is_quota_error(error: Exception) -> bool:
    """Detect Gemini/API quota errors without depending on a specific exception class."""
    text = f"{type(error).__name__}: {error}".lower()
    return (
        "resourceexhausted" in text
        or "resource exhausted" in text
        or "quota" in text
        or "429" in text
        or "too many requests" in text
    )


def extract_retry_seconds(error: Exception) -> int | None:
    """Try to extract retry delay from Gemini error messages."""
    text = str(error)
    patterns = [
        r"retry in ([0-9]+(?:\.[0-9]+)?)s",
        r"retry after ([0-9]+(?:\.[0-9]+)?)s",
        r"retryDelay.*?([0-9]+(?:\.[0-9]+)?)s",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1))))
    return None


def build_quota_message(error: Exception | None = None) -> str:
    retry_seconds = extract_retry_seconds(error) if error is not None else None
    wait_text = f"aguarde cerca de {retry_seconds} segundos" if retry_seconds else "aguarde alguns instantes"

    return (
        "Atingimos temporariamente o limite de uso da API de IA. "
        f"Por favor, {wait_text} e tente enviar sua pergunta novamente.\n\n"
        "Enquanto isso, você ainda pode usar recursos locais da Alice, como análise de CSV/XLSX "
        "e visualização de dashboards, quando eles não dependerem de chamada ao modelo."
    )


def is_ollama_offline_error(error: Exception) -> bool:
    """Detect if Ollama server is offline or unreachable."""
    text = f"{type(error).__name__}: {error}".lower()
    return (
        "connection refused" in text
        or "conexão recusada" in text
        or "ollamaconnectionerror" in text
        or "could not connect to a running ollama" in text
        or "failed to connect to localhost port 11434" in text
    )


def is_ollama_model_missing_error(error: Exception) -> bool:
    """Detect if the requested model is not downloaded in Ollama."""
    text = f"{type(error).__name__}: {error}".lower()
    return (
        "modelnotfound" in text
        or "not found" in text
        or "model" in text and "pull" in text
    )


def build_ollama_error_message(error: Exception) -> str:
    """Return clear, actionable error instructions when Ollama fails."""
    if is_ollama_offline_error(error):
        return (
            "⚠️ **Ollama Offline**: O serviço local de inteligência artificial não está rodando.\n\n"
            "Para iniciar o Ollama, execute no seu terminal:\n"
            "```bash\n"
            "systemctl start ollama\n"
            "# ou\n"
            "ollama serve\n"
            "```\n"
            "Após iniciar o serviço, envie sua pergunta novamente."
        )

    if is_ollama_model_missing_error(error):
        return (
            "⚠️ **Modelo não encontrado no Ollama**: O modelo local configurado ainda não foi baixado.\n\n"
            "Execute no terminal para baixar:\n"
            "```bash\n"
            "ollama pull qwen2.5:3b\n"
            "ollama pull nomic-embed-text\n"
            "```"
        )

    return (
        f"⚠️ **Erro no modelo local (Ollama)**: {error}\n\n"
        "Verifique se o modelo está carregado e se há memória suficiente."
    )
