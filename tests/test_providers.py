"""Tests for LLM and Embedding Providers (Ollama & Gemini)."""

import unittest
from unittest.mock import MagicMock, patch

from src.providers.embedding_provider import OllamaEmbeddingFunction, _l2_normalize, get_embedding_function
from src.providers.llm_provider import (
    BaseLLMProvider,
    OllamaConnectionError,
    OllamaLLMProvider,
    OllamaModelNotFoundError,
    get_llm_provider,
)


class TestProviders(unittest.TestCase):
    def test_l2_normalize_unit_length(self):
        vec = [3.0, 4.0]
        norm_vec = _l2_normalize(vec)
        self.assertAlmostEqual(norm_vec[0], 0.6)
        self.assertAlmostEqual(norm_vec[1], 0.8)

    def test_get_llm_provider_default_ollama(self):
        provider = get_llm_provider()
        self.assertIsInstance(provider, OllamaLLMProvider)
        self.assertEqual(provider.model, "qwen2.5:3b")

    def test_get_embedding_function_ollama(self):
        emb_fn = get_embedding_function()
        self.assertIsInstance(emb_fn, OllamaEmbeddingFunction)
        self.assertEqual(emb_fn.name(), "ollama_embedding_function")

    @patch("urllib.request.urlopen")
    def test_ollama_generate_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"response": "Resposta do Ollama", "done": true}'
        mock_urlopen.return_value = mock_response

        provider = OllamaLLMProvider(base_url="http://localhost:11434", model="qwen2.5:3b")
        result = provider.generate("Olá")
        self.assertEqual(result, "Resposta do Ollama")

    @patch("urllib.request.urlopen")
    def test_ollama_connection_refused(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        provider = OllamaLLMProvider(base_url="http://localhost:11434")
        with self.assertRaises(OllamaConnectionError):
            provider.generate("Olá")


if __name__ == "__main__":
    unittest.main()
