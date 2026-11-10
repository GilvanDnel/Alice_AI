"""Sidebar UI components with Admin features, Sector Filters, and System Metrics."""

from __future__ import annotations

import streamlit as st

from src.admin.auth import validate_admin_login
from src.admin.document_manager import (
    delete_admin_document,
    get_available_sectors,
    list_company_documents,
    save_admin_document,
)
from src.config.settings import (
    ASSISTANT_ROLE_SUMMARY,
    ASSISTANT_TITLE,
    INSTITUTIONAL_CREDIT,
    settings,
)
from src.core.errors import (
    build_ollama_error_message,
    build_quota_message,
    is_ollama_offline_error,
    is_quota_error,
)
from src.core.vector_store import SUPPORTED_DOC_EXTENSIONS, get_vector_store_stats, rebuild_base

ALLOWED_FILE_TYPES = [ext.lstrip(".") for ext in SUPPORTED_DOC_EXTENSIONS]


def render_sidebar() -> None:
    st.sidebar.title(ASSISTANT_TITLE)
    st.sidebar.caption("Assistente Informativa Corporativa")
    st.sidebar.info(ASSISTANT_ROLE_SUMMARY)

    st.sidebar.divider()

    # --- 0. Status do Provedor de IA ---
    provider_name = (settings.llm_provider or "ollama").upper()
    if provider_name == "OLLAMA":
        st.sidebar.success(
            f"🟢 **IA 100% Local (Ollama)**\n"
            f"- Chat: `{settings.ollama_chat_model}`\n"
            f"- Embedding: `{settings.ollama_embedding_model}`"
        )
    else:
        st.sidebar.info(
            f"☁️ **IA Nuvem (Gemini)**\n"
            f"- Chat: `{settings.chat_model}`"
        )

    st.sidebar.divider()

    # --- 1. Filtro de Busca por Setor ---
    st.sidebar.markdown("### Filtro de Busca")
    sectors = get_available_sectors()
    sector_options = ["Todos os setores"] + [s.upper() for s in sectors]

    if "selected_sector_filter" not in st.session_state:
        st.session_state.selected_sector_filter = "Todos os setores"

    selected_filter = st.sidebar.selectbox(
        "Refinar busca por área:",
        sector_options,
        index=sector_options.index(st.session_state.selected_sector_filter)
        if st.session_state.selected_sector_filter in sector_options
        else 0,
        key="sector_filter_selectbox",
    )
    st.session_state.selected_sector_filter = selected_filter

    st.sidebar.divider()

    # --- 2. Painel Admin ---
    with st.sidebar.expander("Painel Admin", expanded=st.session_state.get("admin_authenticated", False)):
        if not st.session_state.get("admin_authenticated"):
            username = st.text_input("Usuário admin", key="admin_user_input")
            password = st.text_input("Senha", type="password", key="admin_pass_input")
            if st.button("Entrar como admin", use_container_width=True):
                if validate_admin_login(username, password):
                    st.session_state.admin_authenticated = True
                    st.success("Admin autenticado.")
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
        else:
            st.success("Sessão Admin Ativa")
            if st.button("Sair / Encerrar Sessão", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.rerun()

            st.divider()

            # --- Dashboard de Métricas da Base ---
            st.markdown("### Métricas da Base")
            try:
                stats = get_vector_store_stats()
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Total Chunks", stats["total_chunks"])
                col_m2.metric("Tamanho DB", f"{stats['db_size_mb']} MB")

                if stats["sector_counts"]:
                    st.caption("Distribuição por setor:")
                    for sec, count in sorted(stats["sector_counts"].items()):
                        st.write(f"- **{sec.upper()}**: {count} chunks")
            except Exception as exc:
                st.caption(f"Não foi possível carregar estatísticas: {exc}")

            st.divider()

            # --- Gerenciamento de Documentos Corporativos ---
            st.markdown("### Adicionar Documento")
            new_file = st.file_uploader(
                "Upload de documento oficial",
                type=ALLOWED_FILE_TYPES,
                key="admin_file_uploader",
                help="Suporta PDF, DOCX, PPTX, Markdown e TXT",
            )
            target_sector = st.selectbox(
                "Setor de destino:",
                sectors if sectors else ["rh", "financeiro", "juridico", "ti", "comercial", "compliance"],
                key="admin_sector_select",
            )
            auto_reindex = st.checkbox("Reindexar base automaticamente após salvar", value=True)

            if st.button("Salvar na Base Corporativa", use_container_width=True, disabled=new_file is None):
                if new_file:
                    saved_path = save_admin_document(new_file, target_sector)
                    st.success(f"Arquivo salvo com sucesso em `{saved_path}`!")
                    if auto_reindex:
                        with st.spinner("Reconstruindo base vetorial com novo documento..."):
                            rebuild_base()
                        st.success("Base reindexada com sucesso!")
                    st.rerun()

            st.divider()

            # --- Lista e Exclusão de Documentos Existentes ---
            st.markdown("### Documentos Cadastrados")
            doc_map = list_company_documents()
            if not doc_map:
                st.info("Nenhum documento cadastrado.")
            else:
                for sector, files in doc_map.items():
                    if files:
                        with st.expander(f"{sector.upper()} ({len(files)})", expanded=False):
                            for fname in files:
                                col1, col2 = st.columns([3, 1])
                                col1.write(f"`{fname}`")
                                if col2.button("Excluir", key=f"del_{sector}_{fname}", help=f"Excluir {fname}"):
                                    if delete_admin_document(sector, fname):
                                        st.success(f"Removido: `{fname}`")
                                        if auto_reindex:
                                            rebuild_base()
                                        st.rerun()
                                    else:
                                        st.error("Erro ao remover arquivo.")

            st.divider()

            # --- Reindexação Manual ---
            st.markdown("### Manutenção")
            st.caption("Reconstrói o índice vetorial no ChromaDB a partir de company_docs/.")
            if st.button("Reindexar Base Inteira", use_container_width=True):
                try:
                    with st.spinner("Reconstruindo base vetorial..."):
                        result = rebuild_base()
                    if result:
                        st.success("Base reconstruída com sucesso!")
                        st.json(result)
                    else:
                        st.info("Nenhum documento encontrado em company_docs/.")
                except Exception as exc:
                    if is_quota_error(exc):
                        st.error(build_quota_message(exc))
                    elif is_ollama_offline_error(exc):
                        st.error(build_ollama_error_message(exc))
                    else:
                        st.error(f"Erro ao reindexar: {exc}")

    st.sidebar.divider()
    st.sidebar.markdown(
        f"""
        <div style="font-size: 0.78rem; text-align: center; opacity: 0.88; line-height: 1.4;">
            <strong>Polo Inova • IFAM CMDI</strong><br/>
            {INSTITUTIONAL_CREDIT}
        </div>
        """,
        unsafe_allow_html=True,
    )
