import unittest
from src.core.rag_engine import _generate_suggested_questions
from src.core.vector_store import get_vector_store_stats
from src.reports.exporters import export_chat_history_pdf, export_chat_history_txt


class TestAdvancedFeatures(unittest.TestCase):
    def test_vector_store_stats(self):
        stats = get_vector_store_stats()
        self.assertIn("total_chunks", stats)
        self.assertIn("sector_counts", stats)
        self.assertIn("db_size_mb", stats)

    def test_generate_suggested_questions(self):
        passages = [{"setor": "rh", "texto": "politica de ferias"}]
        suggestions = _generate_suggested_questions(passages)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("fraciona" in s.lower() for s in suggestions))

    def test_export_chat_history_txt(self):
        messages = [
            {"role": "user", "content": "Quais as regras de férias?"},
            {"role": "assistant", "content": "As férias podem ser fracionadas em até 3 períodos."},
        ]
        txt_bytes = export_chat_history_txt(messages)
        self.assertGreater(len(txt_bytes), 0)
        txt_content = txt_bytes.decode("utf-8")
        self.assertIn("Quais as regras de férias?", txt_content)
        self.assertIn("Alice (Assistente)", txt_content)

    def test_export_chat_history_pdf(self):
        messages = [
            {"role": "user", "content": "Como funciona o reembolso?"},
            {"role": "assistant", "content": "O reembolso de despesas deve ser solicitado em até 5 dias."},
        ]
        pdf_bytes = export_chat_history_pdf(messages)
        self.assertGreater(len(pdf_bytes), 0)


if __name__ == "__main__":
    unittest.main()
