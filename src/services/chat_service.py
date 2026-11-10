"""High-level request orchestration for Alice AI."""

from __future__ import annotations

from dataclasses import dataclass, field
import unicodedata

from src.core.intents import (
    detect_approval_request,
    generic_approval_refusal_response,
    greeting_response,
    identity_response,
    is_greeting,
    is_identity_question,
)
from src.core.router import route_request


@dataclass
class ChatResult:
    mode: str
    answer: str
    sources: list[str]
    payload: object | None = None
    suggested_questions: list[str] = field(default_factory=list)
    source_details: list[dict] = field(default_factory=list)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(char for char in text if not unicodedata.combining(char))


def _is_analytics_followup(question: str) -> bool:
    normalized = _normalize(question)
    triggers = [
        "o que fazer",
        "o que eu faco",
        "o que devo",
        "recomenda",
        "recomendacao",
        "acao",
        "decisao",
        "estrategia",
        "explique",
        "interprete",
        "conclusao",
        "proximo passo",
        "melhor caminho",
        "qual caminho",
    ]
    return any(trigger in normalized for trigger in triggers)


def _build_analytics_answer(analysis) -> str:
    lines = [
        "Analisei a planilha enviada e organizei os principais indicadores para consulta.",
        "",
        "### Leitura executiva",
    ]
    for insight in analysis.insights:
        lines.append(f"- {insight}")

    lines.extend(["", "###Pontos de atenção e sugestões"])
    for recommendation in analysis.recommendations:
        lines.append(f"- {recommendation}")

    lines.extend(
        [
            "",
            "Abaixo estão os KPIs, rankings, evolução temporal (quando houver coluna de data) "
            "e opções de exportação dos relatórios.",
        ]
    )
    return "\n".join(lines)


def handle_message(
    question: str,
    uploaded_file=None,
    first_interaction: bool = False,
    last_analysis=None,
    sector_filter: str | None = None,
    chat_history: list[dict] | None = None,
) -> ChatResult:
    """Route a user message to the appropriate Alice AI module."""
    file_name = getattr(uploaded_file, "name", None)

    if uploaded_file is None:
        if is_identity_question(question):
            return ChatResult(
                mode="identity",
                answer=identity_response(),
                sources=[],
                payload=None,
                suggested_questions=[
                    "Quais são as condições para fracionar as férias?",
                    "Quais são os prazos para reembolso de despesas?",
                ],
                source_details=[],
            )

        if is_greeting(question):
            return ChatResult(
                mode="small_talk",
                answer=greeting_response(question, first_interaction=first_interaction),
                sources=[],
                payload=None,
                suggested_questions=[],
                source_details=[],
            )

        is_approval, has_topic = detect_approval_request(question)
        if is_approval and not has_topic:
            return ChatResult(
                mode="approval_refusal",
                answer=generic_approval_refusal_response(),
                sources=[],
                payload=None,
                suggested_questions=[
                    "Como solicitar o fracionamento de férias?",
                    "Como funciona a solicitação de reembolso?",
                ],
                source_details=[],
            )
    else:
        is_approval = False

    if uploaded_file is None and last_analysis is not None and _is_analytics_followup(question):
        from src.analytics.data_analyzer import build_management_followup_answer

        return ChatResult(
            mode="analytics_followup",
            answer=build_management_followup_answer(question, last_analysis),
            sources=[],
            payload=last_analysis,
            source_details=[],
        )

    mode = route_request(question, uploaded_file_name=file_name)

    if mode == "analytics" and uploaded_file is not None:
        from src.analytics.data_analyzer import analyze_dataframe, load_dataset

        df = load_dataset(uploaded_file, file_name)
        analysis = analyze_dataframe(df)
        return ChatResult(
            mode=mode,
            answer=_build_analytics_answer(analysis),
            sources=[],
            payload=analysis,
            source_details=[],
        )

    if mode == "temporary_document" and uploaded_file is not None:
        from src.services.document_service import ask_temporary_document
        from src.services.upload_service import save_uploaded_file

        temporary_path = save_uploaded_file(uploaded_file)
        answer_text = ask_temporary_document(temporary_path, question=question)
        return ChatResult(
            mode=mode,
            answer=answer_text,
            sources=[],
            payload=temporary_path,
            source_details=[],
        )

    from src.core.rag_engine import ask as ask_knowledge_base

    result = ask_knowledge_base(
        question,
        first_interaction=first_interaction,
        sector_filter=sector_filter,
        chat_history=chat_history,
        approval_request=is_approval,
    )
    return ChatResult(
        mode="knowledge",
        answer=result["resposta"],
        sources=result.get("fontes", []),
        payload=result,
        suggested_questions=result.get("suggested_questions", []),
        source_details=result.get("detalhes_fontes", []),
    )
