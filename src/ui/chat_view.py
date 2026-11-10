"""Chat UI rendering helpers with TTS Audio, Smart Suggestions, and Chat Export."""

from __future__ import annotations

import html

import streamlit as st

from src.analytics.data_analyzer import build_bar_chart, build_time_series_chart
from src.reports.exporters import (
    export_chat_history_pdf,
    export_chat_history_txt,
    export_dataframe_csv,
    export_dataframe_excel,
    export_summary_pdf,
    export_summary_pptx,
)
from src.services.chat_service import ChatResult
from src.utils.source_formatter import format_source_name


def _format_number(value, measure: str | None = None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if measure and any(token in measure.lower() for token in ["valor", "receita", "faturamento", "total"]):
            return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def _render_sources_badges(sources: list[str]) -> None:
    if not sources:
        return

    clean_sources = sorted(list({format_source_name(src) for src in sources}))
    badges_html = []
    for src_name in clean_sources:
        safe_name = html.escape(src_name)
        badges_html.append(
            f'<span class="source-badge">{safe_name}</span>'
        )

    html_block = f"""
    <div style="margin-top: 14px; margin-bottom: 6px;">
        <span style="font-size: 0.82rem; font-weight: 600; opacity: 0.85;">Fontes consultadas:</span>
        <div class="source-badge-container">
            {"".join(badges_html)}
        </div>
    </div>
    """
    st.markdown(html_block, unsafe_allow_html=True)


def _render_source_details_expander(source_details: list[dict] | None) -> None:
    if not source_details:
        return
    with st.expander("Ver trechos consultados na base", expanded=False):
        for detail in source_details:
            title = detail.get("titulo") or detail.get("arquivo") or "Documento"
            sector = detail.get("setor") or "GERAL"
            excerpt = detail.get("trecho") or ""
            review = detail.get("sinalizacao_revisao")
            st.markdown(f"**{title}** (`{sector}`)")
            st.caption(excerpt)
            if review:
                st.warning(review)


def _render_audio_tts_button(text: str) -> None:
    """Render Web Speech API HTML button for instant text-to-speech narration."""
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("\n", " ").replace("'", "\\'")
    tts_html = f"""
    <div style="margin-top: 6px; margin-bottom: 8px;">
        <button onclick="
            var synth = window.speechSynthesis;
            if (synth.speaking) {{ synth.cancel(); return; }}
            var msg = new SpeechSynthesisUtterance('{clean_text[:600]}');
            msg.lang = 'pt-BR';
            synth.speak(msg);
        " style="
            background-color: rgba(59, 130, 246, 0.1);
            color: #3B82F6;
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
        ">
            Ouvir Resposta
        </button>
    </div>
    """
    st.components.v1.html(tts_html, height=42)


def render_suggested_questions(questions: list[str], key_prefix: str) -> str | None:
    """Render interactive follow-up question chips below assistant responses."""
    if not questions:
        return None

    st.markdown(
        "<p style='font-size: 0.85rem; font-weight: 600; opacity: 0.85; margin-top: 10px; margin-bottom: 4px;'>Perguntas Relacionadas:</p>",
        unsafe_allow_html=True,
    )
    clicked_question = None
    cols = st.columns(len(questions))
    for idx, (col, q_text) in enumerate(zip(cols, questions)):
        if col.button(q_text, key=f"{key_prefix}_sug_{idx}", use_container_width=True):
            clicked_question = q_text
    return clicked_question


def render_chat_export_buttons(messages: list[dict]) -> None:
    """Render chat transcript export options in PDF and TXT format."""
    if len(messages) <= 1:
        return

    with st.expander("Baixar Histórico da Conversa", expanded=False):
        col1, col2 = st.columns(2)
        col1.download_button(
            "Baixar Conversa em PDF",
            export_chat_history_pdf(messages),
            "alice_historico_conversa.pdf",
            "application/pdf",
            use_container_width=True,
        )
        col2.download_button(
            "Baixar Conversa em TXT",
            export_chat_history_txt(messages),
            "alice_historico_conversa.txt",
            "text/plain",
            use_container_width=True,
        )


def _render_analytics_panel(analysis, key_prefix: str) -> None:
    measure = analysis.summary.get("medida_principal")

    st.markdown("#### Painel executivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros", analysis.summary.get("linhas", 0))
    col2.metric("Colunas", analysis.summary.get("colunas", 0))
    col3.metric("Total", _format_number(analysis.summary.get("total_medida_principal"), measure))

    if analysis.summary.get("valores_ausentes"):
        st.warning(
            f"Foram encontrados {analysis.summary['valores_ausentes']} valores ausentes. "
            "Use a análise como sinal inicial e valide a base antes de decisões finais."
        )

    if analysis.time_series is not None:
        st.markdown("#### Evolução temporal")
        st.dataframe(analysis.time_series, use_container_width=True)
        figure = build_time_series_chart(analysis.time_series)
        if figure is not None:
            st.plotly_chart(figure, use_container_width=True, key=f"{key_prefix}_time_series")

    for index, (name, ranking) in enumerate(analysis.rankings.items(), start=1):
        title = name.replace("_", " ").title()
        st.markdown(f"#### {title}")
        st.dataframe(ranking, use_container_width=True)
        figure = build_bar_chart(ranking)
        if figure is not None:
            st.plotly_chart(figure, use_container_width=True, key=f"{key_prefix}_ranking_{index}")

    with st.expander("Baixar relatórios da planilha", expanded=False):
        st.download_button(
            "CSV",
            export_dataframe_csv(analysis.dataframe),
            "alice_analise.csv",
            "text/csv",
            key=f"{key_prefix}_csv",
        )
        st.download_button(
            "Excel",
            export_dataframe_excel(analysis.dataframe),
            "alice_analise.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
        )
        st.download_button(
            "PDF executivo",
            export_summary_pdf("Relatório Alice AI", analysis),
            "alice_relatorio.pdf",
            "application/pdf",
            key=f"{key_prefix}_pdf",
        )
        st.download_button(
            "PowerPoint executivo",
            export_summary_pptx("Relatório Alice AI", analysis),
            "alice_relatorio.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key=f"{key_prefix}_pptx",
        )


BLANK_AVATAR = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


def render_history(messages: list[dict]) -> None:
    for index, message in enumerate(messages):
        with st.chat_message(message["role"], avatar=BLANK_AVATAR):
            result = message.get("result")
            if result is not None:
                render_result(result, key_prefix=f"history_{index}")
            else:
                st.markdown(message["content"])


def render_result(result: ChatResult, key_prefix: str = "current") -> str:
    st.markdown(result.answer)

    if result.answer and not result.answer.startswith("Encontrei um erro"):
        _render_audio_tts_button(result.answer)

    if result.sources:
        _render_sources_badges(result.sources)
        _render_source_details_expander(getattr(result, "source_details", None))

    if result.mode == "analytics" and result.payload is not None:
        _render_analytics_panel(result.payload, key_prefix=key_prefix)

    return result.answer
