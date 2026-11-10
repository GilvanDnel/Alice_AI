"""FastAPI backend for Alice AI serving the WebAcademy-styled frontend and RAG/Analytics APIs."""

from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import hmac
from io import BytesIO
import json
from pathlib import Path
import secrets
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.admin.auth import validate_admin_login
from src.admin.document_manager import (
    delete_admin_document,
    get_available_sectors,
    list_company_documents,
    save_admin_document,
)
from src.analytics.data_analyzer import build_bar_chart, build_time_series_chart
from src.config.settings import PROJECT_ROOT, settings
from src.core.errors import (
    build_ollama_error_message,
    build_quota_message,
    is_ollama_model_missing_error,
    is_ollama_offline_error,
    is_quota_error,
)
from src.core.vector_store import (
    ensure_vector_store_populated,
    get_vector_store_stats,
    rebuild_base,
)
from src.reports.exporters import (
    export_chat_history_pdf,
    export_chat_history_txt,
    export_dataframe_csv,
    export_dataframe_excel,
    export_summary_pdf,
    export_summary_pptx,
)
from src.services.chat_service import handle_message
from src.utils.source_formatter import format_source_name

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_vector_store_populated()
    yield


app = FastAPI(
    title=f"{settings.assistant_title} API",
    description=settings.assistant_role_summary,
    version="2.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"

# In-memory session store for last spreadsheet analysis and active admin tokens
_SESSION_ANALYSES: dict[str, Any] = {}
_ADMIN_TOKENS: set[str] = set()
_SERVER_SECRET = secrets.token_hex(32)


class UploadedFileAdapter:
    """Adapter wrapping FastAPI UploadFile bytes into the interface expected by existing services."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self._bytes = content
        self._stream = BytesIO(content)

    def getvalue(self) -> bytes:
        return self._bytes

    def read(self, *args, **kwargs) -> bytes:
        return self._stream.read(*args, **kwargs)

    def seek(self, pos: int, whence: int = 0) -> int:
        return self._stream.seek(pos, whence)


class ChatExportRequest(BaseModel):
    messages: list[dict[str, str]]
    format: str = "pdf"


class AdminLoginRequest(BaseModel):
    username: str
    password: str


def _verify_admin_token(x_admin_token: str | None = Header(default=None)) -> str:
    if not x_admin_token or x_admin_token not in _ADMIN_TOKENS:
        raise HTTPException(status_code=401, detail="Sessão administrativa inválida ou expirada.")
    return x_admin_token


def _serialize_analysis(analysis: Any) -> dict[str, Any]:
    """Convert AnalysisResult (with Pandas DataFrames and Plotly figures) into JSON-friendly dict."""
    rankings_out = []
    for name, df_rank in analysis.rankings.items():
        title = name.replace("_", " ").title()
        fig = build_bar_chart(df_rank)
        rankings_out.append(
            {
                "name": name,
                "title": title,
                "columns": [str(c) for c in df_rank.columns],
                "rows": df_rank.head(10).astype(str).values.tolist(),
                "chart": json.loads(fig.to_json()) if fig is not None else None,
            }
        )

    time_series_out = None
    if analysis.time_series is not None:
        ts_df = analysis.time_series
        ts_fig = build_time_series_chart(ts_df)
        time_series_out = {
            "columns": [str(c) for c in ts_df.columns],
            "rows": ts_df.head(15).astype(str).values.tolist(),
            "chart": json.loads(ts_fig.to_json()) if ts_fig is not None else None,
        }

    return {
        "summary": analysis.summary,
        "insights": analysis.insights,
        "recommendations": analysis.recommendations,
        "rankings": rankings_out,
        "time_series": time_series_out,
    }


@app.get("/api/info")
def get_system_info() -> dict[str, Any]:
    """Return assistant identity, institutional presentation, sectors, and provider status."""
    provider = (settings.llm_provider or "ollama").lower()
    try:
        stats = get_vector_store_stats()
    except Exception:
        stats = {"total_chunks": 0, "sector_counts": {}, "db_size_mb": 0.0}

    return {
        "assistant_name": settings.assistant_name,
        "assistant_title": settings.assistant_title,
        "assistant_role_summary": settings.assistant_role_summary,
        "company_name": settings.company_name,
        "institutional_credit": settings.institutional_credit,
        "provider": {
            "name": provider.upper(),
            "chat_model": settings.ollama_chat_model if provider == "ollama" else settings.chat_model,
            "embedding_model": settings.ollama_embedding_model if provider == "ollama" else settings.embedding_model,
            "local": provider == "ollama",
        },
        "sectors": get_available_sectors(),
        "stats": stats,
    }


@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    question: str | None = Form(default=None),
    sector_filter: str | None = Form(default="Todos os setores"),
    first_interaction: bool = Form(default=False),
    session_id: str = Form(default="default"),
    history: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> JSONResponse:
    """Process a user question (and optional file attachment) through Alice AI."""
    parsed_history: list[dict] = []

    # Also allow application/json requests
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        question = body.get("question", "")
        sector_filter = body.get("sector_filter", "Todos os setores")
        first_interaction = bool(body.get("first_interaction", False))
        session_id = body.get("session_id", "default")
        raw_hist = body.get("history", [])
        if isinstance(raw_hist, list):
            parsed_history = raw_hist
    else:
        if history:
            try:
                parsed_history = json.loads(history)
            except Exception:
                parsed_history = []

    clean_question = (question or "").strip()
    if not clean_question and file is None:
        raise HTTPException(status_code=400, detail="Envie uma pergunta ou anexe um arquivo.")

    uploaded_adapter = None
    if file is not None and file.filename:
        file_bytes = await file.read()
        uploaded_adapter = UploadedFileAdapter(name=file.filename, content=file_bytes)
        if not clean_question:
            clean_question = f"Analise o arquivo {file.filename}"

    last_analysis = _SESSION_ANALYSES.get(session_id)

    try:
        result = handle_message(
            clean_question,
            uploaded_file=uploaded_adapter,
            first_interaction=first_interaction,
            last_analysis=last_analysis,
            sector_filter=sector_filter,
            chat_history=parsed_history,
        )
    except Exception as exc:
        if is_quota_error(exc):
            return JSONResponse(
                {
                    "mode": "quota",
                    "answer": build_quota_message(exc),
                    "sources": [],
                    "formatted_sources": [],
                    "source_details": [],
                    "suggested_questions": [],
                    "analytics": None,
                }
            )
        if is_ollama_offline_error(exc) or is_ollama_model_missing_error(exc):
            return JSONResponse(
                {
                    "mode": "ollama_error",
                    "answer": build_ollama_error_message(exc),
                    "sources": [],
                    "formatted_sources": [],
                    "source_details": [],
                    "suggested_questions": [],
                    "analytics": None,
                }
            )
        return JSONResponse(
            {
                "mode": "error",
                "answer": f"Encontrei um erro ao processar sua consulta: {exc}",
                "sources": [],
                "formatted_sources": [],
                "source_details": [],
                "suggested_questions": [],
                "analytics": None,
            },
            status_code=500,
        )

    analytics_payload = None
    if result.mode == "analytics" and result.payload is not None:
        _SESSION_ANALYSES[session_id] = result.payload
        analytics_payload = _serialize_analysis(result.payload)

    formatted_sources = sorted(list({format_source_name(src) for src in result.sources}))

    return JSONResponse(
        {
            "mode": result.mode,
            "answer": result.answer,
            "sources": result.sources,
            "formatted_sources": formatted_sources,
            "source_details": result.source_details,
            "suggested_questions": result.suggested_questions,
            "analytics": analytics_payload,
        }
    )


@app.post("/api/export/chat")
def export_chat_endpoint(req: ChatExportRequest) -> Response:
    """Export chat transcript in PDF or TXT."""
    fmt = req.format.lower().strip()
    if fmt == "txt":
        data = export_chat_history_txt(req.messages)
        return Response(
            content=data,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="alice_historico_conversa.txt"'},
        )
    data = export_chat_history_pdf(req.messages)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="alice_historico_conversa.pdf"'},
    )


@app.get("/api/export/analytics/{session_id}/{fmt}")
def export_analytics_endpoint(session_id: str, fmt: str) -> Response:
    """Export the last analyzed spreadsheet in CSV, XLSX, PDF, or PPTX."""
    analysis = _SESSION_ANALYSES.get(session_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Nenhuma análise de planilha encontrada nesta sessão.")

    fmt_clean = fmt.lower().strip()
    if fmt_clean == "csv":
        return Response(
            content=export_dataframe_csv(analysis.dataframe),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="alice_analise.csv"'},
        )
    if fmt_clean == "xlsx":
        return Response(
            content=export_dataframe_excel(analysis.dataframe),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="alice_analise.xlsx"'},
        )
    if fmt_clean == "pdf":
        return Response(
            content=export_summary_pdf("Relatório Executivo - Alice AI", analysis),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="alice_relatorio.pdf"'},
        )
    if fmt_clean == "pptx":
        return Response(
            content=export_summary_pptx("Relatório Executivo - Alice AI", analysis),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": 'attachment; filename="alice_relatorio.pptx"'},
        )
    raise HTTPException(status_code=400, detail="Formato de exportação inválido.")


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest) -> dict[str, Any]:
    if not validate_admin_login(req.username, req.password):
        raise HTTPException(status_code=401, detail="Credenciais administrativas inválidas.")
    raw = f"{req.username}:{secrets.token_hex(16)}"
    token = hmac.new(_SERVER_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    _ADMIN_TOKENS.add(token)
    return {"success": True, "token": token}


@app.post("/api/admin/logout")
def admin_logout(token: str = Depends(_verify_admin_token)) -> dict[str, bool]:
    _ADMIN_TOKENS.discard(token)
    return {"success": True}


@app.get("/api/admin/dashboard")
def admin_dashboard(_: str = Depends(_verify_admin_token)) -> dict[str, Any]:
    return {
        "stats": get_vector_store_stats(),
        "documents": list_company_documents(),
        "sectors": get_available_sectors(),
    }


@app.post("/api/admin/upload")
async def admin_upload_document(
    sector: str = Form(...),
    auto_reindex: bool = Form(default=True),
    file: UploadFile = File(...),
    _: str = Depends(_verify_admin_token),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo inválido.")
    content = await file.read()
    adapter = UploadedFileAdapter(name=file.filename, content=content)
    saved_path = save_admin_document(adapter, sector)
    reindexed = None
    if auto_reindex:
        reindexed = rebuild_base()
    return {
        "success": True,
        "saved_path": str(saved_path.name),
        "reindexed": reindexed,
        "stats": get_vector_store_stats(),
        "documents": list_company_documents(),
    }


@app.delete("/api/admin/documents/{sector}/{filename}")
def admin_delete_document(
    sector: str,
    filename: str,
    auto_reindex: bool = True,
    _: str = Depends(_verify_admin_token),
) -> dict[str, Any]:
    deleted = delete_admin_document(sector, filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    if auto_reindex:
        rebuild_base()
    return {
        "success": True,
        "stats": get_vector_store_stats(),
        "documents": list_company_documents(),
    }


@app.post("/api/admin/reindex")
def admin_reindex(_: str = Depends(_verify_admin_token)) -> dict[str, Any]:
    result = rebuild_base()
    return {
        "success": True,
        "result": result,
        "stats": get_vector_store_stats(),
    }


# Serve Frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "Alice AI API ativa. Frontend não localizado."})
