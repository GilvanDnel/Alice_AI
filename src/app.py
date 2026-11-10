"""Main Streamlit app for Alice AI - Informative Corporate RAG Assistant."""

from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.config.settings import (
    ASSISTANT_NAME,
    ASSISTANT_TITLE,
    INSTITUTIONAL_CREDIT,
)
from src.core.errors import (
    build_ollama_error_message,
    build_quota_message,
    is_ollama_model_missing_error,
    is_ollama_offline_error,
    is_quota_error,
)
from src.core.vector_store import ensure_vector_store_populated
from src.services.chat_service import ChatResult, handle_message
from src.ui.chat_view import (
    render_chat_export_buttons,
    render_history,
    render_result,
    render_suggested_questions,
)
from src.ui.sidebar import render_sidebar
from src.ui.styles import load_custom_css

SUPPORTED_UPLOADS = ["pdf", "docx", "pptx", "csv", "xlsx", "md", "txt"]

GREETING_MESSAGE = (
    f"Olá! Sou a {ASSISTANT_NAME}, sua assistente informativa corporativa.\n\n"
    "Consulto os documentos oficiais da base interna para explicar regras, requisitos, "
    "prazos e procedimentos que você precisa seguir. Também posso ler documentos temporários e analisar planilhas.\n\n"
    "Como posso ajudar você hoje?"
)

# 8 Category Cards covering 100% of corporate sectors & data analysis
CATEGORY_OPTIONS = [
    ("Recursos Humanos", "Quais são as políticas de férias e banco de horas da empresa?"),
    ("TI & Acessos", "Quais são as regras de acesso, senhas e segurança em TI?"),
    ("Jurídico & Contratos", "Quais são as orientações sobre contratos e normas jurídicas?"),
    ("Comercial & Vendas", "Como funciona a política comercial e diretrizes de vendas?"),
    ("Atendimento ao Cliente", "Como funciona o atendimento ao cliente e políticas de suporte?"),
    ("Compliance & Ética", "Quais são os princípios do código de conduta e compliance?"),
    ("Financeiro", "Quais são as regras de reembolso de despesas e rotinas financeiras?"),
    ("Análise de Planilhas", "Como faço para você analisar uma planilha CSV ou Excel que eu enviar?"),
]



def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": GREETING_MESSAGE}
        ]
    if "first_question_done" not in st.session_state:
        st.session_state.first_question_done = False
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    if "last_analysis" not in st.session_state:
        st.session_state.last_analysis = None
    if "pending_suggested_question" not in st.session_state:
        st.session_state.pending_suggested_question = None
    if "db_initialized" not in st.session_state:
        ensure_vector_store_populated()
        st.session_state.db_initialized = True


def reset_chat() -> None:
    """Clear chat messages and reset conversation state."""
    st.session_state.messages = [{"role": "assistant", "content": GREETING_MESSAGE}]
    st.session_state.first_question_done = False
    st.session_state.last_analysis = None
    st.session_state.pending_suggested_question = None


def _render_category_buttons():
    """Render executive category cards covering 100% of corporate sectors (mobile-responsive)."""
    st.markdown("#### Áreas de Conhecimento")
    selected_question = None

    row1 = st.columns(4)
    row2 = st.columns(4)
    columns = list(row1) + list(row2)

    for col, (label, question) in zip(columns, CATEGORY_OPTIONS):
        if col.button(label, use_container_width=True):
            selected_question = question

    return selected_question


def _chat_input():
    """Use Streamlit native file-aware chat input when available."""
    try:
        return st.chat_input(
            "Digite sua mensagem ou anexe um arquivo...",
            accept_file=True,
            file_type=SUPPORTED_UPLOADS,
        )
    except TypeError:
        question = st.chat_input(f"Digite sua dúvida para a {ASSISTANT_NAME}...")
        uploaded_file = st.file_uploader("Anexar arquivo", type=SUPPORTED_UPLOADS)
        if question:
            return {"text": question, "files": [uploaded_file] if uploaded_file else []}
        return None


def _extract_input(raw_input):
    if raw_input is None:
        return None, None
    if isinstance(raw_input, dict):
        files = raw_input.get("files") or []
        return raw_input.get("text"), files[0] if files else None

    question = getattr(raw_input, "text", None)
    files = getattr(raw_input, "files", None) or []
    return question, files[0] if files else None


def _handle_message_safely(question: str, uploaded_file):
    sector_filter = st.session_state.get("selected_sector_filter")
    history_before_current = [
        {"role": msg.get("role", ""), "content": msg.get("content", "")}
        for msg in st.session_state.get("messages", [])[1:-1]
    ]
    try:
        return handle_message(
            question,
            uploaded_file=uploaded_file,
            first_interaction=not st.session_state.first_question_done,
            last_analysis=st.session_state.last_analysis,
            sector_filter=sector_filter,
            chat_history=history_before_current,
        )
    except Exception as exc:
        if is_quota_error(exc):
            return ChatResult(
                mode="quota",
                answer=build_quota_message(exc),
                sources=[],
                payload=None,
            )
        if is_ollama_offline_error(exc) or is_ollama_model_missing_error(exc):
            return ChatResult(
                mode="ollama_error",
                answer=build_ollama_error_message(exc),
                sources=[],
                payload=None,
            )
        return ChatResult(
            mode="error",
            answer=(
                f"Encontrei um erro ao processar sua solicitação: {exc}. "
                f"Verifique os logs ou procure o administrador da {ASSISTANT_TITLE}."
            ),
            sources=[],
            payload=None,
        )


def main() -> None:
    st.set_page_config(
        page_title=f"{ASSISTANT_TITLE} - Assistente Informativa Corporativa",
        layout="centered",
    )
    load_custom_css()
    _init_state()
    render_sidebar()

    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title(ASSISTANT_TITLE)
        st.caption("Assistente Informativa Corporativa • Polo Inova IFAM CMDI • AX Academy")
    with header_col2:
        st.write("")
        if st.button("Nova Conversa", help="Reiniciar conversa", use_container_width=True):
            reset_chat()
            st.rerun()

    render_history(st.session_state.messages)

    # Render suggested follow-up questions from the last assistant result
    last_msg = st.session_state.messages[-1] if st.session_state.messages else {}
    last_result = last_msg.get("result")
    suggested_clicked = None
    if last_result and getattr(last_result, "suggested_questions", None):
        suggested_clicked = render_suggested_questions(
            last_result.suggested_questions,
            key_prefix=f"sug_{len(st.session_state.messages)}",
        )

    # Render Chat Export Buttons (PDF & TXT)
    render_chat_export_buttons(st.session_state.messages)

    button_question = None
    if not st.session_state.first_question_done:
        button_question = _render_category_buttons()

    raw_input = _chat_input()
    question, uploaded_file = _extract_input(raw_input)

    if not question and suggested_clicked:
        question = suggested_clicked
        uploaded_file = None

    if not question and button_question:
        question = button_question
        uploaded_file = None

    # Render Fixed Footer at bottom of screen
    current_year = datetime.now().year
    st.markdown(
        f"""
        <div class="app-footer-fixed">
            {ASSISTANT_TITLE} &bull; {current_year} &bull; {INSTITUTIONAL_CREDIT}
        </div>
        """,
        unsafe_allow_html=True,
    )

    BLANK_AVATAR = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=BLANK_AVATAR):
        st.markdown(question)

    with st.chat_message("assistant", avatar=BLANK_AVATAR):
        with st.spinner("Analisando consulta nas fontes oficiais..."):
            result = _handle_message_safely(question, uploaded_file)
            st.session_state.first_question_done = True
            if result.mode == "analytics" and result.payload is not None:
                st.session_state.last_analysis = result.payload
            answer = render_result(result, key_prefix=f"current_{len(st.session_state.messages)}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "result": result,
        }
    )
    st.rerun()


if __name__ == "__main__":
    main()