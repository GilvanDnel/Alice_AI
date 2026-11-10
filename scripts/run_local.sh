#!/usr/bin/env bash
# ==========================================================
# Alice AI - Script de Inicialização Local (FastAPI + Ollama)
# Desenvolvido pelo Polo Inova do IFAM CMDI • AX Academy
# ==========================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

MODE="web"
FORCE_REINDEX="false"

for arg in "$@"; do
    case "$arg" in
        --streamlit)
            MODE="streamlit"
            ;;
        --reindex)
            FORCE_REINDEX="true"
            ;;
    esac
done

echo "=== 1. Verificando ambiente Python ==="
if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual .venv..."
    python3 -m venv .venv
fi

echo "Ativando ambiente virtual..."
source .venv/bin/activate

echo "=== 2. Instalando/Atualizando dependências ==="
pip install -q -r requirements.txt

echo "=== 3. Verificando serviço Ollama ==="
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama não está respondendo. Tentando iniciar serviço..."
    if command -v systemctl > /dev/null 2>&1 && systemctl status ollama > /dev/null 2>&1; then
        sudo systemctl start ollama || true
    else
        echo "Iniciando 'ollama serve' em segundo plano..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi
fi

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama está ativo em http://localhost:11434"
else
    echo "⚠️ Não foi possível conectar ao Ollama. Inicie manualmente com: ollama serve"
fi

echo "=== 4. Garantindo download dos modelos necessários ==="
echo "- Verificando modelo de embeddings: nomic-embed-text..."
ollama pull nomic-embed-text
echo "- Verificando modelo de chat: qwen2.5:3b..."
ollama pull qwen2.5:3b

if [ "$FORCE_REINDEX" = "true" ]; then
    echo "=== 5. Reindexando documentos corporativos (--reindex) ==="
    python3 -m src.core.reindex
fi

if [ "$MODE" = "streamlit" ]; then
    echo "=== 6. Iniciando Alice AI (Interface Streamlit) ==="
    echo "Acesse no navegador em: http://localhost:8501"
    streamlit run src/app.py
else
    echo "=== 6. Iniciando Alice AI (Interface WebAcademy + API FastAPI) ==="
    echo "Acesse no navegador em: http://localhost:8000"
    uvicorn src.api:app --host 0.0.0.0 --port 8000
fi
