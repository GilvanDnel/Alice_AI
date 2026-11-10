"""Initial analytics module for temporary CSV/XLSX uploads."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import plotly.express as px
except ImportError:
    px = None


@dataclass
class AnalysisResult:
    summary: dict[str, Any]
    rankings: dict[str, pd.DataFrame]
    time_series: pd.DataFrame | None
    insights: list[str]
    recommendations: list[str]
    dataframe: pd.DataFrame


def load_dataset(file_obj, file_name: str) -> pd.DataFrame:
    """Load CSV or XLSX from a Streamlit upload or local path."""
    suffix = Path(file_name).suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(file_obj)

    if suffix == ".csv":
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        separators = [None, ",", ";", "\t"]

        for encoding in encodings:
            for sep in separators:
                try:
                    if hasattr(file_obj, "seek"):
                        file_obj.seek(0)
                    if sep is None:
                        df = pd.read_csv(file_obj, encoding=encoding, sep=None, engine="python")
                    else:
                        df = pd.read_csv(file_obj, encoding=encoding, sep=sep)
                    if len(df.columns) > 1 or len(df) <= 1:
                        return df
                except Exception:
                    continue

        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return pd.read_csv(file_obj)

    raise ValueError(f"Formato não suportado para analytics: {suffix}")


def _find_measure_column(df: pd.DataFrame) -> str | None:
    preferred = [
        "valor_total",
        "receita",
        "faturamento",
        "valor",
        "total",
        "quantidade",
    ]
    lower_map = {column.lower(): column for column in df.columns}
    for name in preferred:
        if name in lower_map and pd.api.types.is_numeric_dtype(df[lower_map[name]]):
            return lower_map[name]

    numeric_columns = list(df.select_dtypes(include="number").columns)
    return numeric_columns[0] if numeric_columns else None


def _candidate_dimensions(df: pd.DataFrame) -> list[str]:
    preferred = ["vendedor", "produto", "regiao", "cliente", "categoria", "setor"]
    lower_map = {column.lower(): column for column in df.columns}
    dimensions = [lower_map[name] for name in preferred if name in lower_map]
    if dimensions:
        return dimensions
    return list(df.select_dtypes(include=["object", "string", "category"]).columns[:3])


def _find_date_column(df: pd.DataFrame) -> str | None:
    preferred = ["data", "date", "dt", "mes", "mês", "periodo", "período"]
    lower_map = {column.lower(): column for column in df.columns}
    for name in preferred:
        if name in lower_map:
            return lower_map[name]

    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            return column
        if pd.api.types.is_numeric_dtype(df[column]):
            continue
        parsed = pd.to_datetime(df[column], errors="coerce", dayfirst=True, format="mixed")
        if parsed.notna().mean() >= 0.7:
            return column
    return None


def _format_number(value: float, measure: str | None = None) -> str:
    if measure and any(token in measure.lower() for token in ["valor", "receita", "faturamento", "total"]):
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _build_time_series(df: pd.DataFrame, date_column: str | None, measure: str | None) -> pd.DataFrame | None:
    if not date_column or not measure:
        return None
    working = df.copy()
    working[date_column] = pd.to_datetime(working[date_column], errors="coerce", dayfirst=True, format="mixed")
    working = working.dropna(subset=[date_column])
    if working.empty:
        return None

    working["periodo"] = working[date_column].dt.to_period("M").astype(str)
    return (
        working.groupby("periodo", dropna=False)[measure]
        .sum()
        .reset_index()
        .sort_values("periodo")
    )



def _build_insights(
    summary: dict[str, Any],
    rankings: dict[str, pd.DataFrame],
    time_series: pd.DataFrame | None,
) -> list[str]:
    measure = summary.get("medida_principal")
    insights = []

    if not measure:
        return [
            "O arquivo não possui uma coluna numérica clara para cálculo de KPIs. "
            "A análise ficou limitada à estrutura da base e qualidade dos dados."
        ]

    total = float(summary.get("total_medida_principal", 0))
    insights.append(
        f"A base contém {summary['linhas']} registros e movimenta "
        f"{_format_number(total, measure)} em {measure}."
    )

    if summary.get("valores_ausentes", 0):
        insights.append(
            f"Foram encontrados {summary['valores_ausentes']} valores ausentes. "
            "Antes de tomar decisão final, vale validar esses campos."
        )

    for name, ranking in rankings.items():
        if ranking.empty or len(ranking.columns) < 2:
            continue
        dimension = ranking.columns[0]
        value_column = ranking.columns[1]
        top = ranking.iloc[0]
        top_value = float(top[value_column])
        share = top_value / total if total else 0
        insights.append(
            f"O maior destaque em {dimension} é {top[dimension]}, com "
            f"{_format_number(top_value, measure)} ({share:.1%} do total)."
        )
        if share >= 0.45:
            insights.append(
                f"Há concentração relevante em {top[dimension]}. Isso pode indicar força comercial, "
                "mas também risco de dependência excessiva."
            )
        break

    if time_series is not None and len(time_series) >= 2:
        value_column = time_series.columns[1]
        first_value = float(time_series.iloc[0][value_column])
        last_value = float(time_series.iloc[-1][value_column])
        variation = ((last_value - first_value) / first_value) if first_value else 0
        direction = "crescimento" if variation >= 0 else "queda"
        insights.append(
            f"Na evolução temporal, o último período mostra {direction} de {variation:.1%} "
            "em relação ao primeiro período disponível."
        )

    return insights


def _build_recommendations(
    summary: dict[str, Any],
    rankings: dict[str, pd.DataFrame],
    time_series: pd.DataFrame | None,
) -> list[str]:
    measure = summary.get("medida_principal")
    if not measure:
        return [
            "Padronizar a planilha com colunas como data, vendedor, produto, região, quantidade e valor_total.",
            "Reenviar a base após limpeza para permitir cálculo de KPIs e rankings confiáveis.",
        ]

    recommendations = [
        "Validar os maiores resultados do ranking e identificar quais práticas podem ser replicadas nas equipes com desempenho menor.",
        "Investigar os últimos colocados do ranking antes de definir cobrança: pode haver problema de território, carteira, sazonalidade ou dado incompleto.",
        "Criar uma meta de curto prazo baseada na média atual e acompanhar a evolução semanal ou mensal.",
    ]

    if summary.get("valores_ausentes", 0):
        recommendations.insert(
            0,
            "Corrigir valores ausentes antes de usar a análise como base para decisão executiva.",
        )

    if time_series is not None and len(time_series) >= 2:
        value_column = time_series.columns[1]
        first_value = float(time_series.iloc[0][value_column])
        last_value = float(time_series.iloc[-1][value_column])
        if first_value and last_value < first_value:
            recommendations.insert(
                0,
                "Como houve queda no período analisado, priorizar diagnóstico de causa: produto, região, preço, atendimento ou canal de venda.",
            )
        else:
            recommendations.append(
                "Como existe sinal de crescimento, avaliar aumento de investimento nos segmentos que lideram o ranking."
            )

    return recommendations


def analyze_dataframe(df: pd.DataFrame) -> AnalysisResult:
    """Generate basic KPIs and rankings from a dataframe."""
    measure = _find_measure_column(df)
    date_column = _find_date_column(df)
    summary = {
        "linhas": int(len(df)),
        "colunas": int(len(df.columns)),
        "colunas_numericas": list(df.select_dtypes(include="number").columns),
        "colunas_texto": list(df.select_dtypes(include=["object", "string", "category"]).columns),
        "valores_ausentes": int(df.isna().sum().sum()),
        "medida_principal": measure,
        "coluna_temporal": date_column,
    }

    if measure:
        summary["total_medida_principal"] = float(df[measure].sum())
        summary["media_medida_principal"] = float(df[measure].mean())

    rankings = {}
    if measure:
        for dimension in _candidate_dimensions(df):
            ranking = (
                df.groupby(dimension, dropna=False)[measure]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
                .head(10)
            )
            rankings[f"ranking_por_{dimension}"] = ranking

    time_series = _build_time_series(df, date_column, measure)
    insights = _build_insights(summary, rankings, time_series)
    recommendations = _build_recommendations(summary, rankings, time_series)

    return AnalysisResult(
        summary=summary,
        rankings=rankings,
        time_series=time_series,
        insights=insights,
        recommendations=recommendations,
        dataframe=df,
    )


def build_bar_chart(ranking: pd.DataFrame):
    """Create a Plotly bar chart from a ranking dataframe."""
    if px is None:
        return None
    if ranking.empty or len(ranking.columns) < 2:
        return None
    x_column, y_column = ranking.columns[0], ranking.columns[1]
    figure = px.bar(
        ranking,
        x=x_column,
        y=y_column,
        title=f"{y_column} por {x_column}",
        text_auto=True,
    )
    figure.update_traces(textposition="outside")
    figure.update_layout(
        xaxis_title=x_column,
        yaxis_title=y_column,
        uniformtext_minsize=8,
        uniformtext_mode="hide",
        margin=dict(l=40, r=30, t=60, b=90),
    )
    return figure


def build_time_series_chart(time_series: pd.DataFrame | None):
    """Create a Plotly line chart for temporal evolution."""
    if px is None or time_series is None or time_series.empty or len(time_series.columns) < 2:
        return None
    x_column, y_column = time_series.columns[0], time_series.columns[1]
    figure = px.line(
        time_series,
        x=x_column,
        y=y_column,
        markers=True,
        title=f"Evolução de {y_column} por período",
        text=y_column,
    )
    figure.update_traces(textposition="top center")
    figure.update_layout(
        xaxis_title=x_column,
        yaxis_title=y_column,
        margin=dict(l=40, r=30, t=60, b=60),
    )
    return figure


def build_management_followup_answer(question: str, analysis: AnalysisResult) -> str:
    """Answer follow-up management questions using the last analysis and the active LLM provider."""
    from src.providers.llm_provider import get_llm_provider

    try:
        provider = get_llm_provider()

        rankings_summary = []
        for r_name, r_df in analysis.rankings.items():
            rankings_summary.append(f"{r_name}:\n{r_df.head(5).to_string(index=False)}")
        rankings_text = "\n\n".join(rankings_summary)

        time_text = (
            analysis.time_series.head(10).to_string(index=False)
            if analysis.time_series is not None
            else "Nenhuma série temporal disponível."
        )

        sample_rows = analysis.dataframe.head(10).to_string(index=False)

        prompt = f"""Você é a Alice, assistente virtual informativa da DNEL SOM.
O usuário está fazendo uma pergunta de acompanhamento sobre uma planilha analisada anteriormente.

RESUMO DA PLANILHA:
- Linhas: {analysis.summary.get('linhas')} | Colunas: {analysis.summary.get('colunas')}
- Medida Principal: {analysis.summary.get('medida_principal')}
- Total Medida: {analysis.summary.get('total_medida_principal')}

RANKINGS PRINCIPAIS:
{rankings_text}

EVOLUÇÃO TEMPORAL:
{time_text}

AMOSTRA DOS DADOS:
{sample_rows}

INSIGHTS ANTERIORES:
{chr(10).join(analysis.insights)}

PERGUNTA DE ACOMPANHAMENTO DO USUÁRIO:
{question}

Instruções:
- Responda de forma direta, analítica e executiva com base nos dados apresentados.
- Se a pergunta envolver valores, números ou destaques específicos da base, use os dados reais.
- Mantenha tom profissional.
"""
        return provider.generate(prompt)
    except Exception:
        pass

    lines = [
        "Com base na última análise carregada, eu olharia para três decisões práticas:",
        "",
    ]
    for index, recommendation in enumerate(analysis.recommendations[:3], start=1):
        lines.append(f"{index}. {recommendation}")

    if analysis.insights:
        lines.extend(["", "Leitura executiva:"])
        for insight in analysis.insights[:3]:
            lines.append(f"- {insight}")

    return "\n".join(lines)



def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    return output.getvalue()
