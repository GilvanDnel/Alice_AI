// ==========================================================================
// ALICE AI — APLICAÇÃO CLIENT-SIDE REFINADA (PADRÃO WEB ACADEMY UFAM)
// ==========================================================================

const INITIAL_GREETING =
  "Olá, sou a Alice. Posso ajudar você a consultar as regras, os requisitos e os procedimentos da empresa, ou analisar documentos e planilhas anexados.";

let chatMessages = [];
let firstQuestionDone = false;
let pendingAttachment = null;
let adminToken = null;
const sessionId = "sess_" + Math.random().toString(36).substring(2, 10);

// Bootstrap instances
let toastBootstrap = null;
let sourceDetailsModal = null;

document.addEventListener("DOMContentLoaded", () => {
  const toastEl = document.getElementById("app-toast");
  if (toastEl && window.bootstrap) {
    toastBootstrap = new bootstrap.Toast(toastEl, { delay: 3200 });
  }
  const srcModalEl = document.getElementById("modal-source-details");
  if (srcModalEl && window.bootstrap) {
    sourceDetailsModal = new bootstrap.Modal(srcModalEl);
  }

  initSystemInfo();
  resetConversation(false);
  bindEvents();
});

function showToast(message, variant = "primary") {
  const toastEl = document.getElementById("app-toast");
  const msgEl = document.getElementById("app-toast-message");
  if (!toastEl || !msgEl) return;
  toastEl.className = `toast align-items-center text-bg-${variant} border-0`;
  msgEl.textContent = message;
  if (toastBootstrap) toastBootstrap.show();
}

async function initSystemInfo() {
  try {
    const resp = await fetch("/api/info");
    if (!resp.ok) return;
    const info = await resp.json();

    const providerLabel = document.getElementById("provider-label-text");
    if (providerLabel && info.provider) {
      const modeText = info.provider.local ? "IA Local" : "IA Nuvem";
      providerLabel.textContent = `${modeText} (${info.provider.chat_model})`;
    }
  } catch (err) {
    console.warn("Não foi possível carregar metadados iniciais:", err);
  }
}

function bindEvents() {
  const form = document.getElementById("chat-composer-form");
  const input = document.getElementById("chat-question-input");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitCurrentMessage();
  });

  // Enter envia, Shift+Enter quebra linha
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitCurrentMessage();
    }
  });

  // Auto-ajuste de altura do textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 130) + "px";
  });

  // Atalhos de consulta (Estado Inicial e Modal de Assuntos)
  document.querySelectorAll(".category-shortcut-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-question");
      if (q) sendQuestion(q);
    });
  });

  // Indicador visual de filtro de setor ativo
  const sectorSelect = document.getElementById("sector-filter-select");
  const btnResetSector = document.getElementById("btn-reset-sector-filter");
  if (sectorSelect && btnResetSector) {
    sectorSelect.addEventListener("change", () => {
      updateSectorFilterState();
    });
    btnResetSector.addEventListener("click", () => {
      sectorSelect.value = "Todos os setores";
      updateSectorFilterState();
    });
  }

  // Anexo de arquivo
  const btnAttach = document.getElementById("btn-attach-file");
  const fileInput = document.getElementById("file-upload-input");
  const btnRemoveAttach = document.getElementById("btn-remove-attachment");

  btnAttach.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      setAttachment(fileInput.files[0]);
    }
  });
  btnRemoveAttach.addEventListener("click", () => clearAttachment());

  // Nova Conversa
  document.getElementById("btn-nova-conversa").addEventListener("click", () => {
    resetConversation(true);
  });
  document.getElementById("brand-reset-link").addEventListener("click", (e) => {
    e.preventDefault();
    resetConversation(true);
  });

  // Monitoramento de rolagem para mostrar/ocultar botão "Ir para o final"
  const scrollRegion = document.getElementById("chat-scroll-region");
  const btnScrollBottom = document.getElementById("btn-scroll-bottom");
  if (scrollRegion && btnScrollBottom) {
    scrollRegion.addEventListener("scroll", () => {
      const distanceFromBottom =
        scrollRegion.scrollHeight - scrollRegion.scrollTop - scrollRegion.clientHeight;
      if (distanceFromBottom > 180 && firstQuestionDone) {
        btnScrollBottom.classList.remove("d-none");
      } else {
        btnScrollBottom.classList.add("d-none");
      }
    });

    btnScrollBottom.addEventListener("click", () => {
      scrollRegion.scrollTo({ top: scrollRegion.scrollHeight, behavior: "smooth" });
    });
  }

  // Exportar histórico
  document.getElementById("btn-export-pdf").addEventListener("click", () => exportChatHistory("pdf"));
  document.getElementById("btn-export-txt").addEventListener("click", () => exportChatHistory("txt"));

  // Painel Admin
  document.getElementById("form-admin-login").addEventListener("submit", handleAdminLogin);
  document.getElementById("btn-admin-logout").addEventListener("click", handleAdminLogout);
  document.getElementById("btn-admin-reindex").addEventListener("click", handleAdminReindex);
  document.getElementById("form-admin-upload").addEventListener("submit", handleAdminUpload);
}

function updateSectorFilterState() {
  const sectorSelect = document.getElementById("sector-filter-select");
  const btnResetSector = document.getElementById("btn-reset-sector-filter");
  if (!sectorSelect || !btnResetSector) return;

  const isFiltered = sectorSelect.value !== "Todos os setores";
  sectorSelect.classList.toggle("sector-active", isFiltered);
  btnResetSector.classList.toggle("d-none", !isFiltered);
}

function setAttachment(file) {
  pendingAttachment = file;
  const bar = document.getElementById("attachment-preview-bar");
  const nameEl = document.getElementById("attachment-filename");
  const badgeEl = document.getElementById("attachment-badge-type");

  nameEl.textContent = file.name;
  const ext = file.name.split(".").pop().toLowerCase();
  badgeEl.textContent = ["csv", "xlsx"].includes(ext) ? "Planilha" : "Documento";
  bar.classList.remove("d-none");
}

function clearAttachment() {
  pendingAttachment = null;
  const fileInput = document.getElementById("file-upload-input");
  if (fileInput) fileInput.value = "";
  const bar = document.getElementById("attachment-preview-bar");
  if (bar) bar.classList.add("d-none");
}

function resetConversation(notify = false) {
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
  }
  chatMessages = [{ role: "assistant", content: INITIAL_GREETING }];
  firstQuestionDone = false;
  clearAttachment();

  const viewport = document.getElementById("chat-messages-viewport");
  if (viewport) viewport.innerHTML = "";

  const emptyWelcome = document.getElementById("empty-state-welcome");
  if (emptyWelcome) emptyWelcome.classList.remove("d-none");

  const btnScrollBottom = document.getElementById("btn-scroll-bottom");
  if (btnScrollBottom) btnScrollBottom.classList.add("d-none");

  const input = document.getElementById("chat-question-input");
  if (input) input.focus();

  if (notify) {
    showToast("Nova conversa iniciada.", "primary");
  }
}

function submitCurrentMessage() {
  const input = document.getElementById("chat-question-input");
  const text = input.value.trim();
  if (!text && !pendingAttachment) return;

  input.value = "";
  input.style.height = "auto";
  sendQuestion(text, pendingAttachment);
}

async function sendQuestion(questionText, attachmentFile = null) {
  const displayQuestion =
    questionText || (attachmentFile ? `Analise o arquivo anexado: ${attachmentFile.name}` : "");

  // Ocultar o estado inicial vazio ao iniciar a conversa
  const emptyWelcome = document.getElementById("empty-state-welcome");
  if (emptyWelcome) {
    emptyWelcome.classList.add("d-none");
  }

  // Remover chips de sugestões anteriores para manter o histórico limpo
  document.querySelectorAll(".suggested-chips-wrapper").forEach((el) => el.remove());

  // 1. Adicionar mensagem do usuário na tela e no histórico
  appendUserMessageDOM(displayQuestion, attachmentFile ? attachmentFile.name : null);
  const historyForRequest = chatMessages.slice(-6).map((m) => ({
    role: m.role,
    content: m.content,
  }));
  chatMessages.push({ role: "user", content: displayQuestion });

  // 2. Criar indicador de carregamento da Alice
  const loadingRow = appendLoadingIndicatorDOM();
  const sectorFilter = document.getElementById("sector-filter-select").value;
  const isFirst = !firstQuestionDone;
  firstQuestionDone = true;

  const fileToSend = attachmentFile;
  clearAttachment();

  try {
    const formData = new FormData();
    formData.append("question", displayQuestion);
    formData.append("sector_filter", sectorFilter);
    formData.append("first_interaction", isFirst ? "true" : "false");
    formData.append("session_id", sessionId);
    formData.append("history", JSON.stringify(historyForRequest));
    if (fileToSend) {
      formData.append("file", fileToSend);
    }

    const resp = await fetch("/api/chat", {
      method: "POST",
      body: formData,
    });

    const data = await resp.json();
    loadingRow.remove();

    const answerText = data.answer || "Não foi possível obter resposta.";
    chatMessages.push({ role: "assistant", content: answerText });

    appendAssistantMessageDOM({
      answer: answerText,
      formatted_sources: data.formatted_sources || [],
      source_details: data.source_details || [],
      suggested_questions: data.suggested_questions || [],
      analytics: data.analytics || null,
    });
  } catch (err) {
    loadingRow.remove();
    const errorMsg =
      "Encontrei uma falha de comunicação ao processar sua consulta. Verifique se o serviço está ativo e tente novamente.";
    chatMessages.push({ role: "assistant", content: errorMsg });
    appendAssistantMessageDOM({
      answer: errorMsg,
      formatted_sources: [],
      source_details: [],
      suggested_questions: [],
      analytics: null,
    });
  }
}

function appendUserMessageDOM(text, attachedFileName = null) {
  const viewport = document.getElementById("chat-messages-viewport");
  const row = document.createElement("div");
  row.className = "message-row user";
  row.setAttribute("aria-label", "Sua mensagem");

  const fileBadge = attachedFileName
    ? `<div class="mb-1"><span class="badge bg-white text-primary"><i class="bi bi-paperclip me-1"></i>${escapeHtml(attachedFileName)}</span></div>`
    : "";

  row.innerHTML = `
    <div class="message-bubble">
      ${fileBadge}
      <div>${escapeHtml(text).replace(/\n/g, "<br>")}</div>
    </div>
  `;
  viewport.appendChild(row);
  scrollViewportSmart(row);
}

function appendLoadingIndicatorDOM() {
  const viewport = document.getElementById("chat-messages-viewport");
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="assistant-author-label">Alice</div>
    <div class="typing-indicator">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="ms-1">Consultando documentos...</span>
    </div>
  `;
  viewport.appendChild(row);
  scrollViewportSmart(row);
  return row;
}

function appendAssistantMessageDOM({
  answer,
  formatted_sources,
  source_details,
  suggested_questions,
  analytics,
}) {
  const viewport = document.getElementById("chat-messages-viewport");
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.setAttribute("aria-label", "Resposta da Alice");

  const authorEl = document.createElement("div");
  authorEl.className = "assistant-author-label";
  authorEl.textContent = "Alice";
  row.appendChild(authorEl);

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = renderMarkdownToHtml(answer);
  row.appendChild(bubble);

  // Painel de Analytics (se houver planilha analisada)
  if (analytics) {
    const analyticsNode = buildAnalyticsPanelDOM(analytics);
    row.appendChild(analyticsNode);
  }

  // Rodapé discreto da resposta (Fontes + Ouvir/Copiar + Sugestões)
  const footerActions = document.createElement("div");
  footerActions.className = "assistant-footer-actions";

  const metaBar = document.createElement("div");
  metaBar.className = "response-meta-bar";

  // 1. Grupo de Fontes Consultadas (à esquerda)
  const srcGroup = document.createElement("div");
  srcGroup.className = "sources-inline-group";

  if (formatted_sources && formatted_sources.length > 0) {
    const label = document.createElement("span");
    label.className = "sources-label";
    label.textContent = formatted_sources.length === 1 ? "Fonte:" : "Fontes:";
    srcGroup.appendChild(label);

    formatted_sources.forEach((srcName) => {
      const badge = document.createElement("span");
      badge.className = "badge-prisma";
      badge.innerHTML = `<i class="bi bi-file-earmark-text text-primary"></i> ${escapeHtml(srcName)}`;
      srcGroup.appendChild(badge);
    });

    if (source_details && source_details.length > 0) {
      const detailBtn = document.createElement("button");
      detailBtn.type = "button";
      detailBtn.className = "btn-view-source-details";
      detailBtn.textContent = `Ver trechos (${source_details.length})`;
      detailBtn.addEventListener("click", () => openSourceDetailsModal(source_details));
      srcGroup.appendChild(detailBtn);
    }
  }
  metaBar.appendChild(srcGroup);

  // 2. Botões Utilitários Discretos: Ouvir e Copiar (à direita, sempre acessíveis por teclado e toque)
  if (answer) {
    const utilGroup = document.createElement("div");
    utilGroup.className = "response-utility-btns";

    const ttsBtn = document.createElement("button");
    ttsBtn.type = "button";
    ttsBtn.className = "btn-msg-action";
    ttsBtn.title = "Ouvir leitura em voz alta";
    ttsBtn.innerHTML = `<i class="bi bi-volume-up"></i> <span>Ouvir</span>`;
    ttsBtn.addEventListener("click", () => toggleSpeech(answer, ttsBtn));
    utilGroup.appendChild(ttsBtn);

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "btn-msg-action";
    copyBtn.title = "Copiar texto da resposta";
    copyBtn.innerHTML = `<i class="bi bi-copy"></i> <span>Copiar</span>`;
    copyBtn.addEventListener("click", () => copyResponseText(answer, copyBtn));
    utilGroup.appendChild(copyBtn);

    metaBar.appendChild(utilGroup);
  }

  footerActions.appendChild(metaBar);

  // 3. Chips de Perguntas Relacionadas
  if (suggested_questions && suggested_questions.length > 0) {
    const sugWrapper = document.createElement("div");
    sugWrapper.className = "suggested-chips-wrapper";

    suggested_questions.forEach((qText) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "btn-suggested-chip";
      chip.textContent = qText;
      chip.addEventListener("click", () => sendQuestion(qText));
      sugWrapper.appendChild(chip);
    });
    footerActions.appendChild(sugWrapper);
  }

  row.appendChild(footerActions);
  viewport.appendChild(row);
  scrollViewportSmart(row);
}

function scrollViewportSmart(targetElement) {
  const scrollRegion = document.getElementById("chat-scroll-region");
  if (!scrollRegion || !targetElement) return;
  const elementTop = targetElement.offsetTop;
  scrollRegion.scrollTo({
    top: Math.max(0, elementTop - 20),
    behavior: "smooth",
  });
}

async function copyResponseText(text, btnEl) {
  try {
    await navigator.clipboard.writeText(text);
    const originalHtml = btnEl.innerHTML;
    btnEl.innerHTML = `<i class="bi bi-check2 text-success"></i> <span>Copiado</span>`;
    setTimeout(() => {
      btnEl.innerHTML = originalHtml;
    }, 1800);
  } catch (err) {
    showToast("Não foi possível copiar o texto automaticamente.", "warning");
  }
}

function openSourceDetailsModal(details) {
  const body = document.getElementById("modal-source-details-body");
  if (!body) return;

  body.innerHTML = details
    .map((item, idx) => {
      const reviewAlert = item.sinalizacao_revisao
        ? `<div class="alert alert-warning py-2 px-3 mt-2 mb-0 small">
             <i class="bi bi-exclamation-triangle-fill me-1"></i>
             <strong>Sinalização de Revisão Documental:</strong> ${escapeHtml(item.sinalizacao_revisao)}
           </div>`
        : "";

      return `
        <div class="card border mb-3 shadow-xs">
          <div class="card-header bg-white d-flex justify-content-between align-items-center py-2">
            <div>
              <span class="badge-prisma me-2"><i class="bi bi-file-earmark-text"></i> ${escapeHtml(item.titulo)}</span>
              <span class="badge bg-secondary-subtle text-secondary-emphasis">Setor: ${escapeHtml(item.setor)}</span>
            </div>
            <small class="text-muted font-monospace">Trecho #${idx + 1}</small>
          </div>
          <div class="card-body py-2 px-3">
            <pre class="m-0 small text-secondary" style="white-space: pre-wrap; font-family: 'Inter', sans-serif;">${escapeHtml(item.trecho)}</pre>
            ${reviewAlert}
          </div>
        </div>
      `;
    })
    .join("");

  if (sourceDetailsModal) {
    sourceDetailsModal.show();
  }
}

function toggleSpeech(text, buttonEl) {
  if (!("speechSynthesis" in window)) {
    showToast("Seu navegador não suporta leitura por voz.", "warning");
    return;
  }

  const synth = window.speechSynthesis;
  if (synth.speaking) {
    synth.cancel();
    document.querySelectorAll(".btn-msg-action.speaking").forEach((b) => {
      b.classList.remove("speaking");
      b.innerHTML = `<i class="bi bi-volume-up"></i> <span>Ouvir</span>`;
    });
    return;
  }

  const cleanText = text
    .replace(/[*#>`_~-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 900);

  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.lang = "pt-BR";

  buttonEl.classList.add("speaking");
  buttonEl.innerHTML = `<i class="bi bi-stop-circle"></i> <span>Parar</span>`;

  utterance.onend = () => {
    buttonEl.classList.remove("speaking");
    buttonEl.innerHTML = `<i class="bi bi-volume-up"></i> <span>Ouvir</span>`;
  };
  utterance.onerror = () => {
    buttonEl.classList.remove("speaking");
    buttonEl.innerHTML = `<i class="bi bi-volume-up"></i> <span>Ouvir</span>`;
  };

  synth.speak(utterance);
}

// --------------------------------------------------------------------------
// PAINEL EXECUTIVO DE ANALYTICS (Planilhas CSV / Excel)
// --------------------------------------------------------------------------
function buildAnalyticsPanelDOM(analytics) {
  const wrapper = document.createElement("div");
  wrapper.className = "mt-3 w-100";

  const summary = analytics.summary || {};
  const totalVal =
    typeof summary.total_medida_principal === "number"
      ? summary.total_medida_principal.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : summary.total_medida_principal || "-";

  let html = `
    <div class="row g-2 mb-3">
      <div class="col-4">
        <div class="stat-card py-2 px-3">
          <div class="stat-label"><span>Registros</span><i class="bi bi-table text-primary"></i></div>
          <div class="stat-value fs-5">${summary.linhas || 0}</div>
        </div>
      </div>
      <div class="col-4">
        <div class="stat-card py-2 px-3">
          <div class="stat-label"><span>Colunas</span><i class="bi bi-layout-three-columns text-info"></i></div>
          <div class="stat-value fs-5">${summary.colunas || 0}</div>
        </div>
      </div>
      <div class="col-4">
        <div class="stat-card py-2 px-3">
          <div class="stat-label"><span>Total (${escapeHtml(summary.medida_principal || "Medida")})</span><i class="bi bi-calculator text-success"></i></div>
          <div class="stat-value fs-5">${escapeHtml(String(totalVal))}</div>
        </div>
      </div>
    </div>
    <div class="d-flex flex-wrap gap-2 mb-3">
      <a href="/api/export/analytics/${sessionId}/csv" class="btn btn-outline-primary btn-sm">
        <i class="bi bi-filetype-csv me-1"></i> Baixar CSV
      </a>
      <a href="/api/export/analytics/${sessionId}/xlsx" class="btn btn-outline-success btn-sm">
        <i class="bi bi-file-earmark-excel me-1"></i> Baixar Excel
      </a>
      <a href="/api/export/analytics/${sessionId}/pdf" class="btn btn-outline-danger btn-sm">
        <i class="bi bi-file-earmark-pdf me-1"></i> PDF Executivo
      </a>
      <a href="/api/export/analytics/${sessionId}/pptx" class="btn btn-outline-secondary btn-sm">
        <i class="bi bi-file-earmark-slides me-1"></i> PowerPoint Executivo
      </a>
    </div>
  `;

  wrapper.innerHTML = html;

  if (analytics.rankings && analytics.rankings.length > 0) {
    analytics.rankings.forEach((rk) => {
      if (rk.chart && window.Plotly) {
        const chartDiv = document.createElement("div");
        chartDiv.className = "border rounded-2 bg-white p-2 mb-2";
        chartDiv.style.height = "300px";
        wrapper.appendChild(chartDiv);
        setTimeout(() => {
          Plotly.newPlot(chartDiv, rk.chart.data, rk.chart.layout, { responsive: true, displayModeBar: false });
        }, 50);
      }
    });
  }

  return wrapper;
}

// --------------------------------------------------------------------------
// EXPORTAR HISTÓRICO DA CONVERSA
// --------------------------------------------------------------------------
async function exportChatHistory(format) {
  if (chatMessages.length <= 1) {
    showToast("Envie pelo menos uma pergunta antes de exportar o histórico.", "warning");
    return;
  }

  try {
    const resp = await fetch("/api/export/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatMessages, format }),
    });
    if (!resp.ok) throw new Error("Falha ao exportar histórico.");

    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `alice_historico_conversa.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast(`Histórico exportado em ${format.toUpperCase()} com sucesso!`, "success");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// --------------------------------------------------------------------------
// PAINEL ADMINISTRATIVO
// --------------------------------------------------------------------------
async function handleAdminLogin(e) {
  e.preventDefault();
  const username = document.getElementById("admin-username").value.trim();
  const password = document.getElementById("admin-password").value;
  const errEl = document.getElementById("admin-login-error");
  errEl.classList.add("d-none");

  try {
    const resp = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) {
      throw new Error("Credenciais inválidas.");
    }
    const data = await resp.json();
    adminToken = data.token;
    document.getElementById("admin-login-view").classList.add("d-none");
    document.getElementById("admin-dashboard-view").classList.remove("d-none");
    await loadAdminDashboard();
    showToast("Sessão administrativa autenticada.", "success");
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("d-none");
  }
}

async function handleAdminLogout() {
  if (adminToken) {
    await fetch("/api/admin/logout", {
      method: "POST",
      headers: { "X-Admin-Token": adminToken },
    }).catch(() => {});
  }
  adminToken = null;
  document.getElementById("admin-dashboard-view").classList.add("d-none");
  document.getElementById("admin-login-view").classList.remove("d-none");
  document.getElementById("admin-password").value = "";
}

async function loadAdminDashboard() {
  if (!adminToken) return;
  const resp = await fetch("/api/admin/dashboard", {
    headers: { "X-Admin-Token": adminToken },
  });
  if (!resp.ok) return;
  const data = await resp.json();
  renderAdminStatsAndDocs(data.stats, data.documents);
}

function renderAdminStatsAndDocs(stats, documents) {
  if (stats) {
    document.getElementById("admin-stat-chunks").textContent = stats.total_chunks || 0;
    document.getElementById("admin-stat-size").textContent = `${stats.db_size_mb || 0} MB`;
  }

  const container = document.getElementById("admin-docs-list-container");
  if (!container || !documents) return;

  const sectors = Object.keys(documents);
  if (sectors.length === 0) {
    container.innerHTML = `<p class="text-muted small m-2">Nenhum documento cadastrado.</p>`;
    return;
  }

  container.innerHTML = sectors
    .map((sec) => {
      const files = documents[sec] || [];
      if (files.length === 0) return "";
      const fileRows = files
        .map(
          (fname) => `
          <div class="d-flex justify-content-between align-items-center py-1 px-2 border-bottom small">
            <span class="font-monospace text-dark">${escapeHtml(fname)}</span>
            <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2" onclick="deleteAdminDoc('${escapeHtml(sec)}', '${escapeHtml(fname)}')">
              Excluir
            </button>
          </div>
        `
        )
        .join("");

      return `
        <div class="mb-2">
          <div class="fw-semibold small text-uppercase text-primary bg-light px-2 py-1 rounded-1">
            ${escapeHtml(sec)} (${files.length})
          </div>
          ${fileRows}
        </div>
      `;
    })
    .join("");
}

window.deleteAdminDoc = async function (sector, filename) {
  if (!adminToken) return;
  try {
    const resp = await fetch(`/api/admin/documents/${encodeURIComponent(sector)}/${encodeURIComponent(filename)}`, {
      method: "DELETE",
      headers: { "X-Admin-Token": adminToken },
    });
    if (!resp.ok) throw new Error("Erro ao remover documento.");
    const data = await resp.json();
    renderAdminStatsAndDocs(data.stats, data.documents);
    showToast(`Documento ${filename} removido e base atualizada.`, "success");
  } catch (err) {
    showToast(err.message, "danger");
  }
};

async function handleAdminUpload(e) {
  e.preventDefault();
  if (!adminToken) return;
  const fileInput = document.getElementById("admin-upload-file");
  const sector = document.getElementById("admin-upload-sector").value;
  if (!fileInput.files || fileInput.files.length === 0) return;

  const btn = document.getElementById("btn-admin-upload-submit");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Indexando...`;

  try {
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("sector", sector);
    formData.append("auto_reindex", "true");

    const resp = await fetch("/api/admin/upload", {
      method: "POST",
      headers: { "X-Admin-Token": adminToken },
      body: formData,
    });
    if (!resp.ok) throw new Error("Erro ao enviar documento.");
    const data = await resp.json();
    fileInput.value = "";
    renderAdminStatsAndDocs(data.stats, data.documents);
    showToast("Documento salvo e indexado com sucesso!", "success");
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> Salvar e Indexar`;
  }
}

async function handleAdminReindex() {
  if (!adminToken) return;
  const btn = document.getElementById("btn-admin-reindex");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Reindexando...`;

  try {
    const resp = await fetch("/api/admin/reindex", {
      method: "POST",
      headers: { "X-Admin-Token": adminToken },
    });
    if (!resp.ok) throw new Error("Falha ao reindexar base.");
    const data = await resp.json();
    document.getElementById("admin-stat-chunks").textContent = data.stats.total_chunks || 0;
    document.getElementById("admin-stat-size").textContent = `${data.stats.db_size_mb || 0} MB`;
    showToast("Base vetorial reconstruída com sucesso!", "success");
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i> Reindexar Base`;
  }
}

// --------------------------------------------------------------------------
// UTILITÁRIOS DE FORMATAÇÃO MARKDOWN SEGURO
// --------------------------------------------------------------------------
function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatInlineMarkdown(line) {
  let out = escapeHtml(line);
  out = out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\*(.+?)\*/g, "<em>$1</em>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  return out;
}

function renderMarkdownToHtml(markdownText) {
  const lines = String(markdownText || "").split(/\r?\n/);
  let html = "";
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      html += "</ul>";
      inUl = false;
    }
    if (inOl) {
      html += "</ol>";
      inOl = false;
    }
  };

  for (let rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeLists();
      continue;
    }

    if (line.startsWith("### ")) {
      closeLists();
      html += `<h3>${formatInlineMarkdown(line.slice(4))}</h3>`;
      continue;
    }
    if (line.startsWith("## ")) {
      closeLists();
      html += `<h2>${formatInlineMarkdown(line.slice(3))}</h2>`;
      continue;
    }
    if (line.startsWith("# ")) {
      closeLists();
      html += `<h1>${formatInlineMarkdown(line.slice(2))}</h1>`;
      continue;
    }

    if (line.startsWith("> ")) {
      closeLists();
      html += `<blockquote>${formatInlineMarkdown(line.slice(2))}</blockquote>`;
      continue;
    }

    const ulMatch = line.match(/^[-*•]\s+(.*)/);
    if (ulMatch) {
      if (inOl) {
        html += "</ol>";
        inOl = false;
      }
      if (!inUl) {
        html += "<ul>";
        inUl = true;
      }
      html += `<li>${formatInlineMarkdown(ulMatch[1])}</li>`;
      continue;
    }

    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (inUl) {
        html += "</ul>";
        inUl = false;
      }
      if (!inOl) {
        html += "<ol>";
        inOl = true;
      }
      html += `<li>${formatInlineMarkdown(olMatch[1])}</li>`;
      continue;
    }

    closeLists();
    html += `<p>${formatInlineMarkdown(line)}</p>`;
  }

  closeLists();
  return html || `<p>${escapeHtml(markdownText)}</p>`;
}
