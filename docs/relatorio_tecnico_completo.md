# RELATÓRIO TÉCNICO DE ENGENHARIA, GOVERNANÇA E ARQUITETURA DE RAG
## Projeto: Alice AI — Assistente Informativa Corporativa
**Apresentação Institucional:** Desenvolvido pelo Polo Inova do IFAM CMDI, com participação dos alunos do AX Academy  
**Engenharia e Repositório Base:** Gilvan Silva  
**Organização de Referência na Base Documental:** DNEL SOM Serviços Inteligentes  
**Versão do Sistema:** v2.0 (FastAPI + WebAcademy UI + Ollama Local)


---

## 1. Resumo Executivo e Propósito Corporativo

O **Daniel AI** é uma solução corporativa inteligente de **Geração Aumentada por Recuperação (RAG - Retrieval-Augmented Generation)**, **Analytics de Dados Executivos** e **Escalonamento por Setor**, desenvolvida para atuar como a camada primária e autorizada de acesso ao conhecimento interno da **DNEL SOM Serviços Inteligentes**.

O projeto resolve o problema crônico de descentralização de informações operacionais — espalhadas entre manuais físicos, PDFs heterogêneos, planilhas temporárias e conhecimento tácito de colaboradores —, eliminando inconsistências no atendimento ao cliente (loja física + e-commerce) e acelerando a tomada de decisão gerencial.

### Pilares Fundamentais do Projeto:
1. **Padronização Omnichannel:** Garantir respostas unificadas entre a loja física e o e-commerce.
2. **Eliminação de Alucinações:** O assistente responde **exclusivamente com base no contexto recuperado** de documentos autorizados. Quando a informação não consta na base, o sistema realiza o **escalonamento automático para o e-mail do setor responsável** (*RH, TI, Jurídico, Comercial, Atendimento, Compliance, Financeiro*).
3. **Conformidade Legal e LGPD:** Tratamento de dados pessoais, protocolos de descarte de dados (*Wipe / Format*) em equipamentos deixados para assistência técnica e proteção contra vazamento de informações sensíveis.
4. **Governança de IA:** Camada de segurança lógica para mitigar ataques de engenharia de prompt (*Prompt Injection / Antijailbreak*) sob o princípio do privilégio mínimo.

---

## 2. Catálogo de Artefatos da Base de Conhecimento (`company_docs/`)

Para otimizar o processo de busca vetorial (*vector search*) e reduzir o consumo excessivo de tokens, a base documental foi reestruturada através de um processo de **desmembramento (*sharding*) e modularização**. Os documentos volumosos originais foram fatiados em **10 arquivos Markdown (`.md`) especializados**, distribuídos em 7 pastas setoriais:

| Pasta Setorial | Arquivo (`.md`) | Finalidade Técnica e Conteúdo no Sistema RAG |
| :--- | :--- | :--- |
| `atendimento/` | `faq_clientes.md` | Manual de atendimento ao cliente, fretes digitais/físicos, prazos de suporte, métodos de faturamento e fluxo de acionamento de garantia técnica. |
| `comercial/` | `politica_comercial.md` | Regulamento completo do Programa de Afiliados, comissão padrão (15% digital, 5% físico), regras de divulgação e restrições de marca. |
| `compliance/` | `codigo_de_conduta.md` | Código de ética corporativa, postura digital, uso de EPIs, proteção física de dados e proibição de exposição de clientes em redes sociais. |
| `financeiro/` | `politica_reembolso.md` | Diretrizes de pós-venda para reembolsos/devoluções, direito de arrependimento (7 dias) e prazos de estorno (Cartão, PIX, Boleto). |
| `financeiro/` | `rotinas_financeiras.md` | SOP financeiro para operadores: abertura/sangria de caixa físico, conciliação bancária, chargebacks, combate à fraude e auditoria. |
| `juridico/` | `orientacoes_juridicas.md` | Manual técnico-jurídico de proteção contra garantias indevidas. Define laudos de recusa automática (bobinas queimadas por distorção/clipping, azinhavre por infiltração de água, impedância incompatível). |
| `juridico/` | `politica_contratos.md` | Regras para parcerias lógicas e SLAs de entrega de soluções digitais (24h a 2 dias úteis) e equipamentos físicos (2 a 12 dias úteis). |
| `rh/` | `politica_banco_de_horas.md` | SOP de jornada sob CLT: escala 6x1 de técnicos/analistas, adicionais noturnos, cálculo de banco de horas e regime disciplinar. |
| `rh/` | `politica_de_ferias.md` | SOP para solicitação de descanso anual, regramento de fracionamento em até 3 períodos e trava de escala mínima para atendimento. |
| `ti/` | `manual_acesso.md` | Diretrizes de segurança da informação, controle de credenciais (MFA), alarmes físicos, protocolo antijailbreak de Nível 5 (L5) e contingência. |

---

## 3. Arquitetura do Sistema e Engenharia de Software

A solução foi projetada sob uma **arquitetura estritamente modular** (desacoplada em camadas), garantindo testabilidade automatizada e facilitando a manutenção futura:

```text
Usuário → Interface Streamlit (Mobile-First + CSS) → Router (classificador de intenções)
                                                            │
                 ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
                 ▼                                          ▼                                          ▼
           RAG Engine                                 Analytics Engine                           Escalonamento
     (busca vetorial + RAG +                     (Pandas + Plotly +                          (direcionamento por
      Gemini + filtro por setor +                 Gemini + exportadores                      setor + e-mail de contato)
      citação sanitizada de fontes)               CSV/Excel/PDF/PPTX)
                 │
                 ▼
           ChromaDB (base vetorial persistente,
           embeddings via Gemini API com retry 429)
```

### Componentes das Camadas:
- **Camada de APresentação (`src/ui/`):** Interface web responsiva em Streamlit (`app.py`, `chat_view.py`, `sidebar.py`, `styles.py`), com CSS adaptável a Modo Claro/Escuro, badges de fontes sanitizados, botão de leitura por voz nativa (**Web Speech API TTS**) e cartões interativos para 100% dos setores.
- **Camada de Orquestração (`src/services/`):** `chat_service.py` (roteamento e gerenciamento de estado), `document_service.py` (análise de PDFs/DOCXs temporários via LLM) e `upload_service.py`.
- **Camada de Negócio e RAG (`src/core/`):** `rag_engine.py` (prompting estrito, sugestões dinâmicas de perguntas relacionadas), `vector_store.py` (chunking de 1000 caracteres com overlap de 150, filtro por setor, tratamento de 429), `router.py`, `escalation.py` e `errors.py`.
- **Camada de Administração (`src/admin/`):** `auth.py` (validação de credenciais via `hmac.compare_digest`), `document_manager.py` (listagem, upload por setor e exclusão de arquivos com reindexação) e Dashboard de Métricas de Saúde da Base.
- **Camada de Analytics e Relatórios (`src/analytics/`, `src/reports/`):** `data_analyzer.py` (leitura robusta de CSVs brasileiros, datas `DD/MM/YYYY`, análises temporais e follow-up via IA) e `exporters.py` (exportação segura em CSV, Excel, PDF ReportLab sanitizado e PPTX).

---

## 4. Desafios Técnicos Superados e Soluções de Engenharia

Durante o desenvolvimento e homologação em nuvem, diversos desafios de alta complexidade foram identificados e resolvidos:

### Desafio 1: Estouro de Cota na API do Google Gemini (HTTP 429 Rate Limit)
- **Problema:** A chave gratuita do Gemini possui limite de 100 requisições/minuto para geração de embeddings (`embed_content`). Ao reindexar múltiplos arquivos em sequência, a API retornava erro `429 ResourceExhausted`, interrompendo a reindexação no meio e deixando a base vetorial vazia.
- **Solução:** Implementou-se um algoritmo de **Espera Automática com Retentativas (Exponential Backoff)** na classe `GeminiEmbeddingFunction` em `vector_store.py`. Se a API retornar erro 429, o sistema identifica o tempo de espera necessário (`extract_retry_seconds`), aguarda o tempo determinado e re-executa a requisição até 5 vezes sem quebrar a reindexação.

### Desafio 2: Bug de Filtro Nulo na Busca por Setor (`"Todos os setores"`)
- **Problema:** Ao selecionar a opção padrão "Todos os setores" na interface, a busca RAG passava a string `"Todos os setores"` para o parâmetro `where` do ChromaDB (`where={"setor": "todos os setores"}`). Como nenhum documento pertence a um setor com esse nome, o banco retornava 0 resultados para qualquer pergunta.
- **Solução:** Ajustou-se a verificação do filtro para identificar qualquer expressão iniciada com `"todos"` (`if not s_clean.startswith("todos"):`). Assim, quando "Todos os setores" está selecionado, o filtro é omitido e a busca engloba livremente todos os 7 setores da empresa.

### Desafio 3: Robustez na Leitura de Planilhas CSV Brasileiras (Analytics)
- **Problema:** Arquivos CSV gerados pelo Excel no Brasil costumam vir em codificações `latin-1` / `cp1252` e utilizando ponto e vírgula (`;`) como separador, causando quebra ou leitura em coluna única no `pd.read_csv`.
- **Solução:** Atualizou-se a função `load_dataset` em `data_analyzer.py` para testar múltiplos encodings (`utf-8-sig`, `utf-8`, `latin-1`, `cp1252`) e autodetectar separadores. Além disso, adicionou-se `dayfirst=True` e `format="mixed"` no `pd.to_datetime` para conversão correta de datas brasileiras (`DD/MM/YYYY`).

### Desafio 4: Invisibilidade de Texto em Modo Escuro (Dark Mode CSS)
- **Problema:** Regras estáticas de CSS como `.stApp { background-color: #FAFAFC; }` forçavam o fundo branco enquanto o navegador em Modo Escuro mantinha as fontes em branco, resultando em texto invisível (branco sobre branco).
- **Solução:** Reformulou-se `styles.py` e `chat_view.py` removendo cores estáticas e adotando transparências adaptáveis (`rgba(59, 130, 246, 0.15)`). A interface passou a se adaptar perfeitamente e automaticamente aos temas Claro e Escuro.

---

## 5. Infraestrutura, Deploy e Runbook OCI

A aplicação foi implantada na nuvem **Oracle Cloud Infrastructure (OCI Compute)** em uma instância Ubuntu 24.04 Always Free.

### Especificações do Ambiente de Produção:
- **IP Público:** `163.176.65.156`
- **Porta da Aplicação:** `8501` (TCP)
- **Gerenciador de Processo:** `systemd` (serviço `daniel.service`)
- **Comportamento:** Reinício automático em caso de falha e inicialização no boot da máquina.

### Runbook de Implantação e Manutenção (`daniel.service`):

#### 1. Configuração do Serviço Systemd (`/etc/systemd/system/daniel.service`):
```ini
[Unit]
Description=Daniel AI - Assistente Corporativo DNEL SOM
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Daniel_AI
ExecStart=/home/ubuntu/Daniel_AI/venv/bin/streamlit run src/app.py --server.port 8501
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 2. Comandos Operacionais no Servidor Ubuntu:

```bash
# Entrar no diretório e ativar o ambiente virtual (venv)
cd ~/Daniel_AI
source venv/bin/activate

# Reindexar a base de conhecimento a partir de company_docs/
python -m src.core.reindex

# Recarregar as configurações de serviços e reiniciar o Daniel AI
sudo systemctl daemon-reload
sudo systemctl restart daniel

# Verificar status do serviço e logs em tempo real
sudo systemctl status daniel
sudo journalctl -u daniel -f
```

> **Nota de Segurança & Operação:** O checklist completo de comandos de diagnóstico (`htop`, `uptime`, `ss`), manutenção de Git e acesso via SSH é mantido na pasta privada local `private/` (protegida via `.gitignore`), garantindo a preservação da chave privada SSH e credenciais.


---

## 6. Validação e Qualidade (Testes Automatizados)

A aplicação conta com uma suíte completa de **25 testes unitários automatizados**, implementados sob a biblioteca nativa `unittest`.

### Execução dos Testes:
```bash
python -m unittest discover tests
```

### Cobertura da Suíte de Testes:
1. `TestAdminAuth` e `TestDocumentManager` (`tests/test_admin.py`): Validação de credenciais HMAC, upload de arquivos por setor, listagem e remoção segura.
2. `TestAnalytics` (`tests/test_analytics.py`): Geração de KPIs, leitura de CSVs em `latin-1` com `;` e integridade de relatórios PDF/PPTX.
3. `TestRouter` (`tests/test_router.py`): Validação do roteamento de intenções (RAG x Analytics x Documento Temporário).
4. `TestEscalation` (`tests/test_escalation.py`): Detecção de setores e formatação de e-mails de encaminhamento.
5. `TestIntents` (`tests/test_intents.py`): Classificação de saudações e pequenas conversas.
6. `TestErrors` (`tests/test_errors.py`): Captura de exceções `429 ResourceExhausted` e mensagens amigáveis de cota.
7. `TestSourceFormatter` (`tests/test_source_formatter.py`): Sanitização de nomes de arquivos físicos em títulos institucionais.
8. `TestAdvancedFeatures` (`tests/test_advanced_features.py`): Filtro de busca por setor, métricas do banco vetorial e exportadores de histórico de conversa (PDF/TXT).

**Resultado da Validação:** 100% dos 25 testes executados e aprovados com sucesso (`Ran 25 tests in 0.17s - OK`).

---

## 7. Recomendações de Manutenção e Próximos Passos

1. **Sincronização Periódica de Documentos:** Sempre que uma política corporativa for atualizada em `company_docs/`, acionar a reindexação pelo Painel Admin da interface ou via comando `python -m src.core.reindex` para manter os embeddings sincronizados.
2. **Monitoramento de Cota de IA:** Acompanhar o Painel Admin para verificar o tamanho em MB do banco e a quantidade total de *chunks* indexados.
3. **Auditoria de Segurança:** Manter atualizada a matriz de permissões e chaves da API do Gemini no arquivo `.env`.

---
*Relatório compilado e documentado como registro técnico definitivo de arquitetura e engenharia do Projeto Daniel AI.*
