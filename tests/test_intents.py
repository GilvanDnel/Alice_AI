import unittest
from src.core.intents import (
    detect_approval_request,
    greeting_response,
    identity_response,
    is_greeting,
    is_identity_question,
)


class TestIntents(unittest.TestCase):
    def test_detects_simple_and_compound_greeting(self):
        self.assertTrue(is_greeting("olá"))
        self.assertTrue(is_greeting("ola"))
        self.assertTrue(is_greeting("boa tarde"))
        self.assertTrue(is_greeting("Olá, bom dia."))
        self.assertTrue(is_greeting("Oi, tudo bem?"))

    def test_does_not_treat_question_as_greeting(self):
        self.assertFalse(is_greeting("como solicito férias?"))
        self.assertFalse(is_greeting("Bom dia, como solicito fracionamento de férias?"))

    def test_greeting_response_mirrors_salutation_without_inventing_time(self):
        resp_morning = greeting_response("Olá, bom dia.", first_interaction=True)
        self.assertIn("Bom dia!", resp_morning)
        self.assertNotIn("Boa tarde", resp_morning)
        self.assertIn("Alice", resp_morning)

        resp_neutral = greeting_response("Olá!", first_interaction=True)
        self.assertIn("Olá!", resp_neutral)
        self.assertNotIn("Bom dia", resp_neutral)
        self.assertNotIn("Boa tarde", resp_neutral)
        self.assertNotIn("Boa noite", resp_neutral)

    def test_identity_question_and_response(self):
        self.assertTrue(is_identity_question("Qual é seu nome?"))
        self.assertTrue(is_identity_question("Quem é você?"))
        self.assertFalse(is_identity_question("Qual o prazo de férias?"))
        resp = identity_response()
        self.assertIn("Sou a Alice", resp)
        self.assertIn("informativa", resp)
        self.assertNotIn("Daniel", resp)

    def test_detect_approval_request(self):
        self.assertEqual(detect_approval_request("Você pode aprovar minhas férias?"), (True, True))
        self.assertEqual(detect_approval_request("Alice, autorize meu reembolso"), (True, True))
        self.assertEqual(detect_approval_request("Como solicito o fracionamento de férias?"), (False, False))


if __name__ == "__main__":
    unittest.main()
