"""Lightweight intent detection for greetings, identity, and direct approval requests."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(char for char in text if not unicodedata.combining(char))


_GREETING_TOKENS = {
    "oi",
    "ola",
    "opa",
    "bom",
    "dia",
    "boa",
    "tarde",
    "noite",
    "e",
    "ai",
    "eae",
    "hello",
    "hi",
    "hey",
    "tudo",
    "bem",
    "bom",
    "joia",
    "certo",
    "como",
    "vai",
    "voce",
    "vc",
    "esta",
    "ta",
    "alice",
    "assistente",
    "obrigado",
    "obrigada",
    "valeu",
    "agradecido",
    "agradecida",
}

_GREETING_PHRASES = {
    "oi",
    "ola",
    "bom dia",
    "boa tarde",
    "boa noite",
    "e ai",
    "eae",
    "hello",
    "hi",
    "tudo bem",
    "tudo bom",
    "como vai",
    "obrigado",
    "obrigada",
    "valeu",
}

_BUSINESS_OR_QUERY_KEYWORDS = {
    "ferias",
    "fracionamento",
    "reembolso",
    "despesa",
    "despesas",
    "banco",
    "horas",
    "ponto",
    "extra",
    "extras",
    "garantia",
    "devolucao",
    "estorno",
    "pix",
    "boleto",
    "cartao",
    "comissao",
    "comissoes",
    "afiliado",
    "afiliados",
    "desconto",
    "contrato",
    "contratos",
    "juridico",
    "lgpd",
    "dados",
    "senha",
    "acesso",
    "vpn",
    "rede",
    "conduta",
    "compliance",
    "etica",
    "planilha",
    "csv",
    "excel",
    "relatorio",
    "solicito",
    "solicitar",
    "pedir",
    "aprovar",
    "aprova",
    "autorizar",
    "autoriza",
    "regra",
    "regras",
    "politica",
    "procedimento",
    "prazo",
    "quanto",
    "quantos",
    "onde",
    "quando",
    "quem",
    "qual",
    "quais",
    "posso",
    "pode",
    "preciso",
    "devo",
}


def is_greeting(message: str) -> bool:
    """Detect short and compound social greetings without triggering on business queries."""
    normalized = normalize_text(message)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return False

    if cleaned in _GREETING_PHRASES:
        return True

    words = cleaned.split()
    if len(words) > 7:
        return False

    if any(w in _BUSINESS_OR_QUERY_KEYWORDS for w in words):
        return False

    has_greeting_core = any(
        phrase in cleaned
        for phrase in ("oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "eae", "hello", "hi", "obrigad", "valeu")
    )
    if has_greeting_core and all(w in _GREETING_TOKENS for w in words):
        return True

    return False


def greeting_response(message: str = "", first_interaction: bool = False) -> str:
    """Build a brief, coherent greeting response that mirrors the user's time of day without inventing time."""
    normalized = normalize_text(message)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if any(tok in cleaned for tok in ("obrigado", "obrigada", "valeu", "agradec")):
        return "Por nada! Se precisar consultar mais alguma regra ou procedimento, estou à disposição."

    if "bom dia" in cleaned:
        salutation = "Bom dia!"
    elif "boa tarde" in cleaned:
        salutation = "Boa tarde!"
    elif "boa noite" in cleaned:
        salutation = "Boa noite!"
    else:
        salutation = "Olá!"

    if first_interaction:
        return (
            f"{salutation} Sou a Alice, assistente informativa da DNEL SOM. "
            "Posso explicar regras, requisitos e procedimentos previstos nos nossos documentos internos. "
            "Como posso ajudar você hoje?"
        )

    return (
        f"{salutation} Estou por aqui. Você pode me perguntar sobre políticas e procedimentos "
        "da DNEL SOM ou anexar um arquivo para análise."
    )


def is_identity_question(message: str) -> bool:
    """Detect direct questions about the assistant's name, identity, or role."""
    normalized = normalize_text(message)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    identity_patterns = [
        r"\bqual\s+(e\s+)?(o\s+)?seu\s+nome\b",
        r"\bcomo\s+voce\s+se\s+chama\b",
        r"\bquem\s+e\s+voce\b",
        r"\bvoce\s+e\s+(o\s+daniel|a\s+alice)\b",
        r"\bqual\s+(e\s+)?(a\s+)?sua\s+funcao\b",
        r"\bqual\s+(e\s+)?(o\s+)?seu\s+papel\b",
        r"\bo\s+que\s+voce\s+faz\b",
        r"\bapresentese\b",
        r"\bse\s+apresente\b",
    ]
    return any(re.search(pat, cleaned) for pat in identity_patterns)


def identity_response() -> str:
    """Return Alice's first-person feminine identity and informative role statement."""
    return (
        "Sou a Alice, sua assistente virtual informativa na DNEL SOM. "
        "Estou pronta para ajudar você a consultar nossas políticas internas e compreender "
        "as regras, os requisitos, os documentos necessários e as etapas dos procedimentos corporativos. "
        "Vale lembrar que meu papel é exclusivamente orientativo: não aprovo, autorizo nem registro solicitações."
    )


def detect_approval_request(message: str) -> tuple[bool, bool]:
    """Detect if the user is asking the assistant to approve/authorize/execute a request.

    Returns:
        (is_approval_request, has_specific_corporate_topic)
    """
    normalized = normalize_text(message)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    approval_patterns = [
        r"\b(voce|vc|alice)?\s*(pode|poderia|consegue)\s+(aprovar|autorizar|liberar|abonar|deferir|homologar|validar|conceder)\b",
        r"\b(aprove|aprova|autorize|autoriza|libere|libera|abone|abona)\s+(minhas?|meus?|o\s+meu|a\s+minha|esse|este)\b",
        r"\bpreciso\s+que\s+voce\s+(aprove|autorize|libere|abone)\b",
        r"\bvoce\s+(aprova|autoriza|libera|decide)\b",
    ]
    is_req = any(re.search(pat, cleaned) for pat in approval_patterns)
    if not is_req:
        return False, False

    topic_words = {
        "ferias",
        "fracionamento",
        "reembolso",
        "despesa",
        "despesas",
        "banco",
        "horas",
        "ponto",
        "folga",
        "garantia",
        "estorno",
        "devolucao",
        "contrato",
        "acesso",
        "senha",
        "comissao",
        "desconto",
    }
    words = set(cleaned.split())
    has_topic = bool(words.intersection(topic_words))
    return True, has_topic


def generic_approval_refusal_response() -> str:
    """Response when user asks for approval without specifying which corporate policy/topic."""
    return (
        "Não posso aprovar, autorizar ou registrar solicitações, pois minha função é exclusivamente informativa. "
        "Posso explicar quais são as regras, as condições e o procedimento documentado para o que você deseja solicitar. "
        "Sobre qual assunto (como férias, reembolso, banco de horas ou garantia) você gostaria de consultar as regras?"
    )
