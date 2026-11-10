"""RAG engine for Alice AI supporting Ollama and Gemini."""

from __future__ import annotations

import re
from pathlib import Path

from src.config.settings import settings
from src.core.errors import (
    build_ollama_error_message,
    build_quota_message,
    is_ollama_model_missing_error,
    is_ollama_offline_error,
    is_quota_error,
)
from src.core.escalation import build_escalation_message
from src.core.intents import normalize_text
from src.core.vector_store import has_relevant_context, query as vector_query
from src.providers.llm_provider import (
    LLMError,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    get_llm_provider,
)
from src.utils.source_formatter import format_source_name


SYSTEM_PROMPT = """Você é Alice, assistente virtual informativa da DNEL SOM.
Sua função é consultar os trechos de documentos internos recuperados e explicar ao usuário, em português brasileiro claro, natural e objetivo, as regras, os requisitos, as condições e os procedimentos documentados.

REGRAS DE IDENTIDADE E PAPEL (OBRIGATÓRIAS):
1. Quando se referir a si mesma, use sempre a primeira pessoa e o feminino ("Sou a Alice", "Posso explicar", "Não encontrei").
2. NUNCA fale de si mesma em terceira pessoa ("a Alice", "o Agente Daniel", "fale com o assistente").
3. Seu papel é EXCLUSIVAMENTE informativo: você NÃO autoriza, NÃO aprova, NÃO recusa pedidos, NÃO decide se o usuário tem direito a algo, NÃO realiza triagem e NÃO registra solicitações.
4. Quando o usuário perguntar sobre regras ou procedimentos, use linguagem direta voltada ao usuário ("Para solicitar, você precisa...", "As condições exigidas são...").
5. Se um documento recuperado atribuir etapas operacionais, triagem, autorização ou recusa ao antigo "Agente Daniel", NÃO apresente isso como uma capacidade sua ou de um chatbot. Explique apenas as regras e os responsáveis humanos/setores confiáveis documentados (como Gestor, Gerente de Operações ou RH) e indique brevemente que a referência ao antigo "Agente Daniel" no documento está sinalizada para revisão.
6. Não invente procedimentos, prazos, canais ou responsáveis substitutos que não estejam no texto recuperado.

DIRETRIZES DE QUALIDADE E CONCISÃO:
7. Responda primeiro e diretamente ao que foi perguntado, sem repetir a pergunta do usuário e sem apresentações repetitivas.
8. Explique o suficiente para o usuário compreender o que precisa fazer, sem transformar toda resposta em um texto longo.
9. Use listas curtas quando houver requisitos, condições ou etapas.
10. Use no máximo UM exemplo curto apenas quando ajudar na compreensão.
11. Ao explicar fracionamento de férias, apresente apenas exemplos de divisão real em períodos (como 2 ou 3 períodos respeitando os mínimos de 14 dias em um e 5 dias nos demais). Nunca liste "30 dias corridos de gozo integral" como exemplo de fracionamento, pois gozo integral não é divisão em períodos.
12. Não mencione nomes brutos de arquivos (ex: politica_de_ferias.md) nem extensões (.md, .pdf) no texto da resposta.
{extra_instruction}
"""

APPROVAL_REQUEST_INSTRUCTION = (
    "13. O usuário perguntou se você pode aprovar ou autorizar uma solicitação. "
    "Comece esclarecendo em uma frase curta que sua função é apenas orientar sobre as regras e que você não aprova nem registra pedidos; "
    "em seguida, apresente as condições e o procedimento de aprovação previstos no contexto recuperado."
)

FOLLOWUP_INSTRUCTION = (
    "13. ATENÇÃO — PERGUNTA DE CONTINUAÇÃO: O usuário está fazendo uma pergunta complementar sobre o tema anterior. "
    "Responda EXCLUSIVAMENTE ao ponto específico perguntado agora (em no máximo 2 parágrafos curtos ou tópicos diretos). "
    "PROIBIDO repetir explicações, listas de regras de fracionamento ou etapas que já foram ditas na resposta anterior."
)

# Keywords associated with each document stem to avoid cross-document noise in citations
DOC_TOPIC_KEYWORDS: dict[str, set[str]] = {
    "politica_de_ferias": {
        "ferias", "fracionamento", "fracionar", "parcelar", "parcelamento", "aquisitivo",
        "concessivo", "abono", "pecuniario", "vender", "coletivas", "gozo", "14", "30", "60",
    },
    "politica_banco_de_horas": {
        "banco", "horas", "ponto", "extra", "extras", "compensacao", "folga", "jornada", "atraso", "batida",
    },
    "manual_acesso": {
        "senha", "senhas", "acesso", "acessos", "ti", "vpn", "rede", "wifi", "mfa", "2fa",
        "autenticacao", "bloqueio", "credencial", "credenciais", "servidor", "vlan",
    },
    "orientacoes_juridicas": {
        "garantia", "defeito", "vicio", "reparo", "assistencia", "juridico", "cdc", "consumidor",
        "queima", "bobina", "clipping", "laudo", "bancada",
    },
    "politica_contratos": {
        "contrato", "contratos", "sla", "entrega", "rescisao", "multa", "afiliado", "afiliados",
        "equalizacao", "preset", "dsp", "propriedade", "intelectual",
    },
    "codigo_de_conduta": {
        "conduta", "etica", "compliance", "assedio", "conflito", "interesse", "brinde", "brindes",
        "denuncia", "inconformidade", "postura", "vestimenta", "sigilo",
    },
    "rotinas_financeiras": {
        "caixa", "sangria", "faturamento", "pix", "boleto", "cartao", "conciliacao", "chargeback",
        "antifraude", "tesouraria", "nota", "fiscal", "nf",
    },
    "politica_reembolso": {
        "reembolso", "estorno", "devolucao", "arrependimento", "despesa", "despesas", "frete",
        "logistica", "reversa", "comprovante", "avaria",
    },
    "politica_comercial": {
        "comercial", "vendas", "venda", "comissao", "comissoes", "desconto", "descontos",
        "cupom", "cupons", "parceiro", "meta", "metas", "catalogo", "preco",
    },
    "faq_clientes": {
        "cliente", "clientes", "faq", "pedido", "pedidos", "retirada", "loja", "rastreamento",
        "envio", "prazo", "compra", "atendimento",
    },
}


def _extract_tokens(text: str) -> set[str]:
    norm = normalize_text(text)
    words = re.findall(r"[a-z0-9]{3,}", norm)
    stopwords = {
        "como", "para", "que", "qual", "quais", "onde", "quando", "quem", "por", "uma", "uns",
        "umas", "dos", "das", "nos", "nas", "pelo", "pela", "pelos", "pelas", "com", "sem",
        "sobre", "entre", "ate", "mais", "menos", "muito", "pode", "posso", "devo", "preciso",
        "fazer", "funciona", "empresa", "dnel", "som", "alice", "daniel", "agente", "sistema",
        "politica", "regras", "regra", "procedimento", "solicitar", "solicito", "solicitacao",
        "hoje", "agora", "existe", "existem", "tem", "tenho", "ter", "sao", "ser", "esta",
    }
    return {w for w in words if w not in stopwords}


def _build_Contextual_query(question: str, chat_history: list[dict] | None) -> tuple[str, bool]:
    """If the question is a follow-up, enrich the vector search query with previous user context."""
    if not chat_history:
        return question, False

    user_messages = [
        m.get("content", "").strip()
        for m in chat_history
        if m.get("role") == "user" and m.get("content", "").strip()
    ]
    if user_messages and normalize_text(user_messages[-1]) == normalize_text(question):
        user_messages = user_messages[:-1]

    if not user_messages:
        return question, False

    q_tokens = _extract_tokens(question)
    norm_q = normalize_text(question)

    # Detect if current question is short or uses continuation cues
    continuation_cues = (
        "e se ", "e como", "e qual", "e quais", "e quando", "e quem", "nesse caso",
        "nessa situacao", "disso", "dessa", "desse", "sobre isso", "dividir", "parcelar",
        "quantos", "quantas", "aprova", "autoriza", "prazo", "documento", "excecao",
    )
    is_followup = len(q_tokens) <= 4 or any(cue in norm_q for cue in continuation_cues)

    if is_followup:
        last_user_q = user_messages[-1]
        return f"{last_user_q} {question}", True

    return question, False


def _select_supporting_passages(question: str, passages: list[dict], search_query: str = "") -> list[dict]:
    """Filter retrieved passages to keep only those that genuinely support the query topic."""
    if not passages:
        return []

    relevant = [p for p in passages if p.get("distancia", 999) <= settings.rag_max_distance]
    if not relevant:
        return []

    best_distance = min(p.get("distancia", 999) for p in relevant)
    query_tokens = _extract_tokens(f"{question} {search_query}")

    # Score each source document by topic keyword overlap and distance proximity
    doc_scores: dict[str, int] = {}
    for passage in relevant:
        fonte = passage.get("fonte", "")
        stem = Path(fonte).stem.lower()
        topic_kw = DOC_TOPIC_KEYWORDS.get(stem, set())
        passage_tokens = _extract_tokens(passage.get("texto", ""))

        topic_hits = len(query_tokens.intersection(topic_kw)) * 3
        text_hits = len(query_tokens.intersection(passage_tokens))
        score = topic_hits + text_hits
        doc_scores[fonte] = max(doc_scores.get(fonte, 0), score)

    top_source = relevant[0].get("fonte", "")
    top_source_score = doc_scores.get(top_source, 0)
    max_any_score = max(doc_scores.values(), default=0)

    # If no retrieved passage shares any domain/lexical token with the query,
    # treat as out-of-scope unless the semantic distance is extremely close (< 0.25).
    if query_tokens and max_any_score == 0 and best_distance > 0.25:
        return []

    selected = []
    for passage in relevant:
        fonte = passage.get("fonte", "")
        dist = passage.get("distancia", 999)
        score = doc_scores.get(fonte, 0)

        # Always keep passages from the best-matching document if within reasonable distance
        if fonte == top_source and dist <= best_distance + 0.08 and (score > 0 or best_distance <= 0.36):
            selected.append(passage)
            continue

        # Only include a second document if it also has strong lexical/topic overlap with the question
        if dist <= best_distance + 0.04 and score > 0 and score >= (top_source_score * 0.6):
            selected.append(passage)

    return selected


def _answer_indicates_no_info(answer: str) -> bool:
    norm = normalize_text(answer[:200])
    no_info_cues = (
        "nao encontrei",
        "nao ha informac",
        "nao ha trechos",
        "nao ha mencao",
        "nao consta",
        "nao possuo",
        "nenhum dos trechos",
        "nao se referem",
        "peco desculpas, mas nao",
        "desculpe, mas parece",
    )
    return any(cue in norm for cue in no_info_cues)


def _filter_sources_by_answer(answer: str, passages: list[dict], question: str) -> list[dict]:
    """Verify which retrieved passages actually support the generated answer statements."""
    if not passages or _answer_indicates_no_info(answer):
        return []

    unique_sources = {p.get("fonte") for p in passages}
    if len(unique_sources) <= 1:
        return passages

    answer_tokens = _extract_tokens(answer)
    question_tokens = _extract_tokens(question)
    combined_tokens = answer_tokens.union(question_tokens)

    source_relevance: dict[str, int] = {}
    for passage in passages:
        fonte = passage.get("fonte", "")
        stem = Path(fonte).stem.lower()
        topic_kw = DOC_TOPIC_KEYWORDS.get(stem, set())
        p_tokens = _extract_tokens(passage.get("texto", ""))

        overlap = len(answer_tokens.intersection(p_tokens)) + (len(combined_tokens.intersection(topic_kw)) * 3)
        source_relevance[fonte] = max(source_relevance.get(fonte, 0), overlap)

    best_score = max(source_relevance.values()) if source_relevance else 0
    if best_score == 0:
        # Keep only the primary source
        primary = passages[0].get("fonte")
        return [p for p in passages if p.get("fonte") == primary]

    kept_sources = {
        src for src, score in source_relevance.items()
        if score >= max(2, int(best_score * 0.5))
    }
    filtered = [p for p in passages if p.get("fonte") in kept_sources]
    return filtered if filtered else [passages[0]]


def _has_legacy_agent_attribution(text: str) -> bool:
    norm = normalize_text(text)
    return "agente daniel" in norm or "sistema/agente daniel" in norm or "pelo assistente daniel" in norm


def _prepare_passage_text_for_llm(text: str) -> str:
    """Annotate legacy references in prompt context so the 3B model does not impersonate or attribute authority to 'Agente Daniel'."""
    cleaned = text
    # Prevent the 3B model from copying 'Opção C: 1 período de 30 dias (gozo integral padrão)' as a 'fractioning' example
    cleaned = re.sub(
        r"-\s*[_*]*Op[çc][ãa]o C:[_*]*\s*1 per[íi]odo de 30 dias \(gozo integral padr[ãa]o\)\.?",
        "(Nota: 30 dias corridos em período único corresponde ao gozo integral padrão, e não a um fracionamento).",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Replace legacy '3.2 Fluxo de Solicitação via Agente Daniel' block (even if chunk ends before 3.3)
    cleaned = re.sub(
        r"### 3\.2 Fluxo de Solicita[çc][ãa]o via Agente Daniel[\s\S]*?(?=### 3\.3|\Z)",
        (
            "### 3.2 Fluxo de Solicitação e Aprovação Documentado\n\n"
            "- **Etapas confiáveis documentadas:** Verificação do período aquisitivo acumulado, indicação das datas desejadas, "
            "verificação de ausência de conflito de escala na equipe, aprovação pelo **Gerente de Operações ou Gerente Geral** "
            "e emissão do **Aviso de Férias pelo RH**.\n"
            "- **Inconsistência sinalizada para revisão:** O documento original atribui a consulta inicial e triagem ao antigo "
            "assistente virtual (que é apenas informativo e não registra nem autoriza pedidos); confirme com o RH o canal oficial para protocolo.\n\n"
        ),
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"1\.\s*\*\*Consulta de Saldo:\*\*[^\n]*",
        "1. **Verificação de Saldo:** Verificação do período aquisitivo acumulado (canal formal em revisão junto ao RH).",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\(Recusado pelo Sistema/Agente Daniel\)",
        "(Não permitido pelas regras da política)",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bAgente Daniel\b",
        "sistema interno legado (sinalizado para revisão documental)",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _build_context(passages: list[dict]) -> str:
    parts = []
    for idx, passage in enumerate(passages, start=1):
        titulo = format_source_name(passage["fonte"])
        texto_llm = _prepare_passage_text_for_llm(passage["texto"])
        parts.append(
            f"[Trecho {idx} | Documento: {titulo} | Setor: {passage['setor'].upper()}]\n{texto_llm}"
        )
    return "\n\n---\n\n".join(parts)


def _build_history_block(chat_history: list[dict] | None) -> str:
    if not chat_history:
        return ""
    recent = chat_history[-4:]
    lines = []
    for msg in recent:
        role_label = "Usuário" if msg.get("role") == "user" else "Assistente (Alice)"
        content = msg.get("content", "").strip()
        if not content:
            continue
        # Sanitize any legacy self-identification in old history so the model stays consistent as Alice
        content = re.sub(r"\bEu sou o Daniel\b", "Sou a Alice", content, flags=re.IGNORECASE)
        content = re.sub(r"\bSou o Daniel\b", "Sou a Alice", content, flags=re.IGNORECASE)
        lines.append(f"{role_label}: {content[:350]}")
    if not lines:
        return ""
    return "\nHISTÓRICO RECENTE DA CONVERSA:\n" + "\n".join(lines) + "\n"


def _postprocess_alice_answer(
    answer: str,
    question: str,
    passages: list[dict],
    approval_request: bool = False,
) -> str:
    """Ensure the generated answer strictly adheres to Alice's first-person feminine informative role."""
    text = answer.strip()

    # Remove accidental third-person references to Alice or Daniel as an authority
    text = re.sub(
        r"\b(pelo sistema ou agente daniel|pelo agente daniel|ou agente daniel)\b",
        "pelas regras da política",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(o agente daniel|agente daniel)\b",
        "o fluxo legado descrito no documento",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(fale com a alice|conversar com a alice|se a alice autorizar|aprovado pela alice|recusado pela alice)\b",
        "seguir os critérios da política junto ao setor responsável",
        text,
        flags=re.IGNORECASE,
    )
    # Remove raw file extensions if mentioned
    text = re.sub(r"\b[\w_]+\.(md|pdf|docx|pptx|txt)\b", "documento da política", text, flags=re.IGNORECASE)

    # If the user asked how to request/approve and the underlying passage had legacy 'Agente Daniel' workflow,
    # append a clear, non-repetitive note flagging the document inconsistency if not already mentioned
    norm_q = normalize_text(question)
    asks_procedure_or_approval = any(
        tok in norm_q
        for tok in ("solicito", "solicitar", "solicitacao", "pedir", "aprovar", "aprova", "autoriza", "procedimento", "como faco")
    )
    has_legacy_in_passages = any(_has_legacy_agent_attribution(p.get("texto", "")) for p in passages)

    if (asks_procedure_or_approval or approval_request) and has_legacy_in_passages:
        norm_ans = normalize_text(text)
        if "revisao" not in norm_ans and "agente daniel" not in norm_ans:
            text += (
                "\n\n> **Nota sobre o documento:** A política original menciona etapas operacionais associadas ao antigo "
                "*\"Agente Daniel\"* (sinalizado para revisão documental). Como assistente informativa, não realizo "
                "abertura, triagem nem aprovação de pedidos — a validação e aprovação formal cabem ao gestor responsável e ao setor competente."
            )

    if approval_request:
        norm_ans = normalize_text(text[:220])
        if not any(w in norm_ans for w in ("nao aprovo", "nao posso aprovar", "nao autorizo", "informativa", "orientar")):
            prefix = (
                "Como assistente virtual, minha função é orientar sobre as normas internas — "
                "eu não aprovo, autorizo nem registro solicitações.\n\n"
            )
            text = prefix + text

    return text


def _build_source_details(passages: list[dict]) -> list[dict]:
    """Build structured source details for UI traceability."""
    details = []
    seen_files = set()
    for p in passages:
        fname = p.get("fonte", "desconhecida")
        titulo = format_source_name(fname)
        setor = p.get("setor", "geral").upper()
        trecho = p.get("texto", "").strip()
        has_legacy = _has_legacy_agent_attribution(trecho)
        key = (fname, trecho[:80])
        if key in seen_files:
            continue
        seen_files.add(key)
        details.append(
            {
                "arquivo": fname,
                "titulo": titulo,
                "setor": setor,
                "distancia": round(float(p.get("distancia", 0.0)), 4),
                "trecho": trecho[:450] + ("..." if len(trecho) > 450 else ""),
                "sinalizacao_revisao": (
                    "Este trecho faz referência ao legado 'Agente Daniel' como etapa operacional; "
                    "ponto sinalizado para revisão documental."
                    if has_legacy
                    else None
                ),
            }
        )
    return details


def _generate_suggested_questions(passages: list[dict]) -> list[str]:
    sectors = {p.get("setor", "").lower() for p in passages}
    suggestions = []
    if "rh" in sectors:
        suggestions.extend(["Quais são as condições para fracionar as férias?", "Como funcionam as regras do banco de horas?"])
    if "ti" in sectors:
        suggestions.extend(["Quais os requisitos para criar ou redefinir senha?", "Quais são as regras de segurança de acesso em TI?"])
    if "juridico" in sectors:
        suggestions.extend(["Quais são os prazos e requisitos para acionar a garantia?", "Quais as regras da política de contratos?"])
    if "comercial" in sectors:
        suggestions.extend(["Quais são as regras de comissões para afiliados?", "Como funciona a política comercial?"])
    if "atendimento" in sectors:
        suggestions.extend(["Qual o prazo de liberação para retirada na loja física?", "Quais são os canais de atendimento ao cliente?"])
    if "compliance" in sectors:
        suggestions.extend(["Quais as diretrizes do código de conduta?", "Como relatar uma inconformidade ou conflito?"])
    if "financeiro" in sectors:
        suggestions.extend(["Quais são os prazos e condições para reembolso?", "Quais os comprovantes exigidos no atendimento financeiro?"])

    if not suggestions:
        suggestions = ["Quais são as políticas internas da empresa?", "Como entrar em contato com o setor responsável?"]

    return list(dict.fromkeys(suggestions))[:2]


def ask(
    question: str,
    first_interaction: bool = False,
    sector_filter: str | None = None,
    chat_history: list[dict] | None = None,
    approval_request: bool = False,
) -> dict:
    search_query, is_followup = _build_Contextual_query(question, chat_history)

    try:
        raw_passages = vector_query(search_query, sector_filter=sector_filter)
    except Exception as exc:
        if is_quota_error(exc):
            return {
                "resposta": build_quota_message(exc),
                "fontes": [],
                "detalhes_fontes": [],
                "encaminhado": False,
                "quota_exceeded": True,
                "suggested_questions": [],
            }
        if is_ollama_offline_error(exc) or is_ollama_model_missing_error(exc) or isinstance(exc, (OllamaConnectionError, OllamaModelNotFoundError)):
            return {
                "resposta": build_ollama_error_message(exc),
                "fontes": [],
                "detalhes_fontes": [],
                "encaminhado": False,
                "suggested_questions": [],
            }
        raise

    if not has_relevant_context(raw_passages):
        escalation_msg = build_escalation_message(question)
        if approval_request:
            escalation_msg = (
                "Como assistente informativa, não realizo aprovação nem autorização de solicitações. "
                + escalation_msg
            )
        return {
            "resposta": escalation_msg,
            "fontes": [],
            "detalhes_fontes": [],
            "encaminhado": True,
            "suggested_questions": [],
        }

    passages = _select_supporting_passages(question, raw_passages, search_query=search_query)
    if not passages:
        escalation_msg = build_escalation_message(question)
        if approval_request:
            escalation_msg = (
                "Como assistente informativa, não realizo aprovação nem autorização de solicitações. "
                + escalation_msg
            )
        return {
            "resposta": escalation_msg,
            "fontes": [],
            "detalhes_fontes": [],
            "encaminhado": True,
            "suggested_questions": [],
        }

    extra_instructions = []
    if approval_request:
        extra_instructions.append(APPROVAL_REQUEST_INSTRUCTION)
    elif is_followup:
        extra_instructions.append(FOLLOWUP_INSTRUCTION)

    system_text = SYSTEM_PROMPT.format(
        extra_instruction="\n".join(extra_instructions)
    )
    history_block = _build_history_block(chat_history)

    prompt = f"""{history_block}
TRECHOS DOS DOCUMENTOS INTERNOS PARA CONSULTA:
{_build_context(passages)}

PERGUNTA ATUAL DO USUÁRIO:
{question}

Explique de forma direta, objetiva e fiel aos trechos acima o que o usuário precisa saber ou fazer, seguindo todas as regras de identidade da Alice:"""

    provider = get_llm_provider()

    try:
        raw_answer = provider.generate(prompt=prompt, system_prompt=system_text)
    except (OllamaConnectionError, OllamaModelNotFoundError, OllamaTimeoutError, LLMError) as exc:
        return {
            "resposta": build_ollama_error_message(exc),
            "fontes": [],
            "detalhes_fontes": [],
            "encaminhado": False,
            "suggested_questions": [],
        }
    except Exception as exc:
        if is_quota_error(exc):
            return {
                "resposta": build_quota_message(exc),
                "fontes": [],
                "detalhes_fontes": [],
                "encaminhado": False,
                "quota_exceeded": True,
                "suggested_questions": [],
            }
        if is_ollama_offline_error(exc) or is_ollama_model_missing_error(exc):
            return {
                "resposta": build_ollama_error_message(exc),
                "fontes": [],
                "detalhes_fontes": [],
                "encaminhado": False,
                "suggested_questions": [],
            }
        raise

    supporting_passages = _filter_sources_by_answer(raw_answer, passages, question)
    final_answer = _postprocess_alice_answer(
        raw_answer,
        question=question,
        passages=supporting_passages,
        approval_request=approval_request,
    )

    # Strictly validate sources against retrieved supporting passages
    allowed_files = {p["fonte"] for p in raw_passages if "fonte" in p}
    verified_sources = sorted({p["fonte"] for p in supporting_passages if p.get("fonte") in allowed_files})
    source_details = _build_source_details(supporting_passages)

    return {
        "resposta": final_answer,
        "fontes": verified_sources,
        "detalhes_fontes": source_details,
        "encaminhado": False,
        "suggested_questions": _generate_suggested_questions(supporting_passages),
    }
