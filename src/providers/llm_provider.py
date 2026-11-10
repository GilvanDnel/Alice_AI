"""LLM provider abstraction supporting Ollama (local) and Gemini (cloud)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Generator
import urllib.error
import urllib.request

from src.config.settings import settings


class LLMError(Exception):
    """Base error for LLM providers."""


class OllamaConnectionError(LLMError):
    """Raised when Ollama server is unreachable."""


class OllamaModelNotFoundError(LLMError):
    """Raised when the requested Ollama model is missing."""


class OllamaTimeoutError(LLMError):
    """Raised when Ollama request times out."""


class BaseLLMProvider(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate full completion text."""

    @abstractmethod
    def stream_generate(self, prompt: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        """Stream completion tokens."""

    @abstractmethod
    def health_check(self) -> dict[str, str | bool]:
        """Verify provider availability and active model."""


class OllamaLLMProvider(BaseLLMProvider):
    """Ollama local LLM provider using direct HTTP for maximum reliability and zero external lock-in."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_chat_model
        self.timeout = timeout or settings.ollama_timeout

    def _post_json(self, endpoint: str, payload: dict, stream: bool = False):
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.URLError as exc:
            reason_str = str(exc.reason).lower()
            if "connection refused" in reason_str or "conexão recusada" in reason_str:
                raise OllamaConnectionError(
                    f"Ollama não está respondendo em {self.base_url}. "
                    "Verifique se o serviço está ativo ('ollama serve' ou 'systemctl status ollama')."
                ) from exc
            if "timed out" in reason_str:
                raise OllamaTimeoutError(
                    f"Tempo limite ({self.timeout}s) excedido ao aguardar resposta do Ollama."
                ) from exc
            raise LLMError(f"Erro ao comunicar com o Ollama: {exc.reason}") from exc
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404 or "not found" in err_body.lower():
                raise OllamaModelNotFoundError(
                    f"Modelo '{self.model}' não encontrado no Ollama. Execute: 'ollama pull {self.model}'."
                ) from exc
            raise LLMError(f"Erro HTTP {exc.code} do Ollama: {err_body}") from exc

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = self._post_json("/api/generate", payload, stream=False)
        try:
            body = json.loads(response.read().decode("utf-8"))
            return body.get("response", "").strip()
        finally:
            response.close()

    def stream_generate(self, prompt: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = self._post_json("/api/generate", payload, stream=True)
        try:
            for line in response:
                if not line:
                    continue
                try:
                    data = json.loads(line.decode("utf-8"))
                    yield data.get("response", "")
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        finally:
            response.close()

    def health_check(self) -> dict[str, str | bool]:
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                model_ready = any(self.model in m for m in models)
                return {
                    "provider": "ollama",
                    "status": "online" if model_ready else "model_missing",
                    "model": self.model,
                    "available_models": models,
                    "ready": model_ready,
                }
        except Exception as exc:
            return {
                "provider": "ollama",
                "status": "offline",
                "model": self.model,
                "error": str(exc),
                "ready": False,
            }


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini cloud LLM provider."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.google_api_key
        self.model_name = model or settings.chat_model
        if not self.api_key:
            raise EnvironmentError("GOOGLE_API_KEY não configurada no arquivo .env.")

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        res = self._model.generate_content(full_prompt)
        return res.text.strip()

    def stream_generate(self, prompt: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        res = self._model.generate_content(full_prompt, stream=True)
        for chunk in res:
            if chunk.text:
                yield chunk.text

    def health_check(self) -> dict[str, str | bool]:
        return {
            "provider": "gemini",
            "status": "configured" if self.api_key else "missing_key",
            "model": self.model_name,
            "ready": bool(self.api_key),
        }


def get_llm_provider() -> BaseLLMProvider:
    """Factory function returning the configured LLM provider."""
    provider_name = (settings.llm_provider or "ollama").lower().strip()
    if provider_name == "gemini":
        return GeminiLLMProvider()
    return OllamaLLMProvider()
