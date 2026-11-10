# 🤖 Alice AI — Assistente Corporativa RAG

> Assistente virtual informativa baseada em **RAG (Retrieval-Augmented Generation)**, com execução **100% local via Ollama** e interface web inspirada no design system do **WebAcademy**.

🏛️ **Apresentação Institucional:**  
*Desenvolvido pelo **Polo Inova do IFAM CMDI**, com participação dos alunos do **AX Academy**.*

---

## ⚡ Como Executar (Quickstart)

### Opção 1: Via Script Automatizado (Recomendado)
Configura ambiente, valida modelos do Ollama e inicia o servidor:
```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```
Acesse no navegador: **`http://localhost:8000`**

*Flags úteis:*
* `--streamlit`: Inicia a versão legada em Streamlit (`http://localhost:8501`).
* `--reindex`: Força a reconstrução do índice vetorial do ChromaDB.

<details>
<summary><b>Opção 2: Passo a Passo Manual</b></summary>

1. **Garantir modelos locais no Ollama:**
   ```bash
   ollama pull nomic-embed-text
   ollama pull qwen2.5:3b
   ```
2. **Ambiente Python & Dependências:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configuração (.env):**
   ```bash
   cp .env.example .env
   ```
4. **Execução:**
   ```bash
   uvicorn src.api:app --host 0.0.0.0 --port 8000
   ```
</details>

---

## 🎯 Propósito e Papel da Assistente

Alice atua com foco **estritamente informativo e orientativo**:

| O que a Alice FAZ ✅ | O que a Alice NÃO FAZ ❌ |
| :--- | :--- |
| Explica regras, requisitos e etapas documentadas em `company_docs/` | **Não** autoriza, aprova ou recusa solicitações |
| Analisa documentos anexados (PDF, DOCX, TXT) e planilhas (CSV, XLSX) | **Não** substitui gestores, RH ou instâncias de decisão |
| Cita exclusivamente as fontes que sustentam a resposta | **Não** protocola ou abre chamados no lugar do usuário |
| Responde em primeira pessoa do feminino com tom direto | **Não** inventa regras ausentes na base documental |

---

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia | Papel |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Bootstrap 5.3, JS | Interface limpa e desacoplada inspirada no WebAcademy |
| **Backend** | Python 3.10+, **FastAPI**, Uvicorn | API REST, orquestração RAG e streaming/serviço |
| **LLM Local** | **Ollama (`qwen2.5:3b`)** | Geração textual e raciocínio 100% offline |
| **Embeddings** | **Ollama (`nomic-embed-text`)** | Vetorização semântica com normalização L2 |
| **Banco Vetorial**| **ChromaDB** | Armazenamento e busca por similaridade de cosseno |
| **Analytics & Docs**| Pandas, Plotly, ReportLab, python-docx | Análise de planilhas e exportação PDF/TXT/XLSX |

---

## 🧩 Arquitetura Simplificada

```text
Usuário ──► Frontend WebAcademy (FastAPI Static)
                     │
                     ▼
             API REST (FastAPI)
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
Intent Router & RAG Engine    Analytics Engine (Pandas/Plotly)
       │
       ▼
   ChromaDB ◄─── Embeddings (nomic-embed-text via Ollama)
       │
       ▼
  Geração LLM (qwen2.5:3b via Ollama) ──► Resposta com Fontes Citadas
```

---

## 🧪 Testes Automatizados

O projeto conta com suíte de testes unitários e de aceitação para intenções, RAG, rotas e integridade:
```bash
.venv/bin/pytest tests/ -v
```

---

## 📜 Créditos e Referências

* **Institucional:** Polo Inova do IFAM CMDI & AX Academy.
* **Referência de Design:** Projetos do programa WebAcademy (IComp / UFAM).
* **Engenharia Inicial:** Gilvan Silva ([@GilvanDnel](https://github.com/GilvanDnel)).
