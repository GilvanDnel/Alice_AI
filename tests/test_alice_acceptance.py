"""Acceptance tests for Alice AI identity, RAG quality, source filtering, and FastAPI WebAcademy endpoints."""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from src.api import app
from src.config.settings import (
    ASSISTANT_NAME,
    ASSISTANT_TITLE,
    INSTITUTIONAL_CREDIT,
)
from src.core.rag_engine import (
    _postprocess_alice_answer,
    _prepare_passage_text_for_llm,
    _select_supporting_passages,
)
from src.services.chat_service import handle_message


class TestAliceAcceptance(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_centralized_identity_and_credits(self):
        self.assertEqual(ASSISTANT_NAME, "Alice")
        self.assertEqual(ASSISTANT_TITLE, "Alice AI")
        self.assertIn("Polo Inova do IFAM CMDI", INSTITUTIONAL_CREDIT)
        self.assertIn("AX Academy", INSTITUTIONAL_CREDIT)

    def test_greeting_returns_zero_sources_and_no_invented_time(self):
        res = handle_message("Olá, bom dia.", first_interaction=True)
        self.assertEqual(res.mode, "small_talk")
        self.assertEqual(res.sources, [])
        self.assertEqual(res.source_details, [])
        self.assertIn("Bom dia!", res.answer)
        self.assertNotIn("Boa tarde", res.answer)
        self.assertIn("Sou a Alice", res.answer)

    def test_identity_question_returns_alice_in_feminine_first_person(self):
        res = handle_message("Qual é seu nome?", first_interaction=False)
        self.assertEqual(res.mode, "identity")
        self.assertEqual(res.sources, [])
        self.assertIn("Sou a Alice", res.answer)
        self.assertNotIn("Sou o Daniel", res.answer)
        self.assertNotIn("Agente Daniel", res.answer)

    def test_supporting_passages_excludes_unrelated_secondary_docs(self):
        passages = [
            {
                "texto": "Política de Férias: O fracionamento em até 3 períodos exige 14 dias no primeiro período.",
                "fonte": "rh/politica_de_ferias.md",
                "setor": "rh",
                "distancia": 0.22,
                "possui_inconsistencia_legada": True,
            },
            {
                "texto": "Política de Banco de Horas: Horas extras acumuladas devem ser compensadas em até 6 meses.",
                "fonte": "rh/politica_banco_de_horas.md",
                "setor": "rh",
                "distancia": 0.35,
                "possui_inconsistencia_legada": False,
            },
        ]
        selected = _select_supporting_passages("Como solicito o fracionamento de férias?", passages)
        sources = [p["fonte"] for p in selected]
        self.assertIn("rh/politica_de_ferias.md", sources)
        self.assertNotIn("rh/politica_banco_de_horas.md", sources)

    def test_passage_preparation_and_postprocessing_removes_legacy_authority_and_30d_fractioning(self):
        raw_chunk = (
            "Opção A: 14 dias + 16 dias\n"
            "- **Opção C:** 1 período de 30 dias (gozo integral padrão)\n"
            "### 3.2 Fluxo de Solicitação via Agente Daniel\n"
            "O colaborador deve conversar com o Agente Daniel."
        )
        prepared = _prepare_passage_text_for_llm(raw_chunk)
        self.assertNotIn("Opção C", prepared)
        self.assertNotIn("via Agente Daniel", prepared)

        raw_answer = "Para solicitar, você deve conversar com o Agente Daniel."
        cleaned = _postprocess_alice_answer(
            raw_answer,
            "Como solicito o fracionamento de férias?",
            passages=[{"texto": raw_chunk, "fonte": "rh/politica_de_ferias.md"}],
        )
        self.assertNotIn("você deve conversar com o Agente Daniel", cleaned)
        self.assertIn("Nota sobre o documento", cleaned)

    def test_fastapi_info_and_frontend_serving(self):
        resp_info = self.client.get("/api/info")
        self.assertEqual(resp_info.status_code, 200)
        data = resp_info.json()
        self.assertEqual(data["assistant_name"], "Alice")
        self.assertEqual(data["assistant_title"], "Alice AI")
        self.assertIn("Polo Inova do IFAM CMDI", data["institutional_credit"])

        resp_html = self.client.get("/")
        self.assertEqual(resp_html.status_code, 200)
        self.assertIn("Alice AI", resp_html.text)
        self.assertIn("Polo Inova do IFAM CMDI", resp_html.text)
        self.assertNotIn("Desenvolvido por Gilvan Silva", resp_html.text)

    def test_fastapi_chat_greeting_and_identity(self):
        resp_greet = self.client.post(
            "/api/chat",
            data={"question": "Olá, bom dia.", "session_id": "test_sess"},
        )
        self.assertEqual(resp_greet.status_code, 200)
        body = resp_greet.json()
        self.assertEqual(body["mode"], "small_talk")
        self.assertEqual(body["sources"], [])
        self.assertIn("Bom dia!", body["answer"])

        resp_id = self.client.post(
            "/api/chat",
            data={"question": "Qual é seu nome?", "session_id": "test_sess"},
        )
        self.assertEqual(resp_id.status_code, 200)
        body_id = resp_id.json()
        self.assertEqual(body_id["mode"], "identity")
        self.assertEqual(body_id["sources"], [])
        self.assertIn("Sou a Alice", body_id["answer"])

    def test_refined_ui_structure_and_assets(self):
        resp_html = self.client.get("/")
        self.assertEqual(resp_html.status_code, 200)
        html = resp_html.text

        # 1. Regions and short placeholder
        self.assertIn('class="app-shell"', html)
        self.assertIn('class="context-bar"', html)
        self.assertIn('id="empty-state-welcome"', html)
        self.assertIn("Olá, sou a Alice.", html)
        self.assertIn('placeholder="Pergunte à Alice..."', html)
        self.assertIn("Assuntos da base", html)
        self.assertIn("Sobre o papel da Alice", html)

        # 2. CSS coordinated widths and single scroll shell
        resp_css = self.client.get("/css/style.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn("--layout-max-width: 1040px", resp_css.text)
        self.assertIn("--reading-max-width: 820px", resp_css.text)
        self.assertIn("100dvh", resp_css.text)

        # 3. JS clean labels (no redundant 'Você' or 'Alice • Assistente Informativa' per message)
        resp_js = self.client.get("/js/app.js")
        self.assertEqual(resp_js.status_code, 200)
        self.assertNotIn("<span>Você</span>", resp_js.text)
        self.assertNotIn("Alice &bull; Assistente Informativa", resp_js.text)
        self.assertIn("copyResponseText", resp_js.text)


if __name__ == "__main__":
    unittest.main()
