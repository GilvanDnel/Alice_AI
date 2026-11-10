# Alice AI — Assistente Informativa Corporativa (RAG)

Assistente virtual informativa baseada em **RAG (Retrieval-Augmented Generation)** para consulta de normas, regras, requisitos e procedimentos corporativos internos, com execução **100% local via Ollama** e interface web inspirada no sistema de design do **WebAcademy**.

🏛️ **Apresentação Institucional:**  
**Desenvolvido pelo Polo Inova do IFAM CMDI, com participação dos alunos do AX Academy.**

---

## Papel e Identidade da Assistente (Alice)

A **Alice** (`Alice AI`) atua em papel **exclusivamente informativo e orientativo**:

- **O que a Alice faz:**
  - Recupera informações dos documentos corporativos oficiais (`company_docs/`) e explica de forma clara, direta e em primeira pessoa do feminino:
    - O que o colaborador precisa cumprir;
    - Quais condições, prazos e requisitos se aplicam;
    - Quais etapas deve seguir e a quem encaminhar a solicitação conforme documentado;
  - Analisa documentos temporários anexados na conversa (PDF, DOCX, PPTX, TXT, MD) e planilhas de dados (CSV, XLSX);
  - Exibe apenas as fontes documentais que efetivamente sustentam a resposta, permitindo inspecionar os trechos consultados.
- **O que a Alice NÃO faz:**
  - Não autoriza solicitações, não aprova nem recusa pedidos;
  - Não decide se o usuário tem direito a benefícios nem substitui gestores, RH ou setores responsáveis;
  - Não registra, protocola ou executa solicitações;
  - Sinaliza de forma transparente eventuais inconsistências documentais legadas para revisão, sem inventar responsáveis substitutos.

---

## Principais Funcionalidades

- 🎨 **Interface WebAcademy Desacoplada (`frontend/` + FastAPI `src/api.py`):**
  - Construída com os tokens visuais e componentes dos projetos **WebAcademy** (`--primary-blue: #0071bc`, `--bemol-blue: #007cc2`, `--bemol-yellow: #ffb800`, Bootstrap 5.3.3, Bootstrap Icons e tipografia `Inter`);
  - Layout flexível em 2 colunas sem sobreposição do rodapé ou da caixa de mensagem sobre o histórico;
  - Modal de ** Fontes Consultadas** com visualização dos trechos recuperados e sinalização de revisão documental;
  - Painel de Analytics com gráficos interativos Plotly e exportação de relatórios.
- 🦙 **Privacidade & Execução 100% Local (Ollama):**
  - Roda localmente com aceleração por GPU (`qwen2.5:3b` para geração/chat e `nomic-embed-text` para embeddings L2-normalizados no ChromaDB), sem depender de chaves de API externas.
- 💬 **Continuidade Conversacional e Filtragem Rigorosa de Fontes:**
  - Suporta perguntas de acompanhamento (*follow-up*) mantendo o contexto da conversa;
  - Saudações e perguntas de identidade não acionam busca vetorial nem exibem fontes falsas;
  - Filtra documentos secundários para citar apenas as políticas que sustentam a resposta.
- 🔊 **Acessibilidade e Exportação:**
  - Narração por voz nativa (`pt-BR` via Web Speech API) e exportação da conversa em PDF e TXT (`alice_historico_conversa.pdf` / `.txt`).
- 🔑 **Painel Administrativo Autenticado:**
  - Gerenciamento de documentos por setor, métricas da base vetorial e reindexação sob demanda.

---

## Arquitetura do Sistema

```text
Usuário → Frontend WebAcademy (Bootstrap 5 + JS) / Streamlit
                         │
                         ▼
          FastAPI Backend (src/api.py) / Chat Service
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
  Intent Filter      RAG Engine     Analytics Engine
 (Saudação, ID,   (Histórico + Filtro  (Pandas + Plotly +
  Papel/Alçadas)   Semântico de Fontes) Exportadores)
                         │
                         ▼
             ChromaDB + Ollama Local
        ├── Chat: qwen2.5:3b
        └── Embeddings: nomic-embed-text (L2 Cosine)
```

---

## Tecnologias Utilizadas

| Camada | Tecnologia Principal | Alternativa / Suporte |
| :--- | :--- | :--- |
| **Frontend Principal** | HTML5 + CSS3 WebAcademy (`#0071bc`) + Bootstrap 5.3 + JS | Streamlit (`src/app.py`) |
| **Backend / API** | Python 3.10+ • **FastAPI** + Uvicorn (`src/api.py`) | Camada de Serviços modular |
| **LLM Local** | **Ollama (`qwen2.5:3b`)** | Google Gemini (opcional via `.env`) |
| **Embeddings** | **Ollama (`nomic-embed-text`)** | Gemini Embeddings (opcional) |
| **Banco Vetorial** | **ChromaDB** (persistente em `./chroma_db`) | Distância Cosseno + L2 Norm |
| **Analytics & Docs** | Pandas, Plotly, ReportLab (PDF), python-pptx, pypdf, python-docx | Exportação CSV/XLSX/PDF/PPTX |

---

## Como Executar Localmente

### Opção 1: Script Automatizado (Recomendado)

```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

- A interface principal **WebAcademy (FastAPI)** abrirá em: **`http://localhost:8000`**
- Para iniciar na interface alternativa **Streamlit**, use: `./scripts/run_local.sh --streamlit` (`http://localhost:8501`)
- Para forçar a reindexação completa da base documental: `./scripts/run_local.sh --reindex`

### Opção 2: Passo a Passo Manual

1. **Verifique o serviço Ollama e os modelos locais:**
   ```bash
   systemctl status ollama
   curl http://localhost:11434/api/tags
   ollama pull nomic-embed-text
   ollama pull qwen2.5:3b
   ```

2. **Ative o ambiente virtual e instale as dependências:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure o arquivo `.env` (se necessário):**
   ```bash
   cp .env.example .env
   ```

4. **Inicie o servidor FastAPI (Interface WebAcademy):**
   ```bash
   uvicorn src.api:app --host 0.0.0.0 --port 8000
   ```
   Acesse **`http://localhost:8000`** no navegador.

---

## Testes Automatizados

Para executar a suíte completa de testes unitários e de aceitação (identidade da Alice, intenções, filtragem de fontes, endpoints FastAPI, analytics e provedores):

```bash
.venv/bin/pytest tests/ -v
```

---

## Créditos Institucionais e Autoria Técnica

- **Apresentação Institucional:**  
  Desenvolvido pelo **Polo Inova do IFAM CMDI**, com participação dos alunos do **AX Academy**.
- **Referência Visual e Técnica de Interface:**  
  Projetos do programa **WebAcademy** (IComp / UFAM).
- **Repositório Base e Engenharia Inicial:**  
  Gilvan Silva ([@GilvanDnel](https://github.com/GilvanDnel)).
