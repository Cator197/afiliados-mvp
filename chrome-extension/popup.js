const statusBoxElement = document.getElementById('popup-status-box');
const statusElement = document.getElementById('status-text');
const detailsElement = document.getElementById('status-details');
const noteElement = document.getElementById('status-note');
const urlElement = document.getElementById('current-url');
const simulateButton = document.getElementById('simulate-btn');
const copyLinkButton = document.getElementById('copy-link-btn');
const checkButton = document.getElementById('check-page-btn');
const openSiteButton = document.getElementById('open-site-btn');

const BACKEND_BASE_URL = 'https://minhaoferta.com';
const SIMULATED_DELAY_MS = 1400;
const SIMULATED_LINK = 'https://minhaoferta.com/link-simulado';

let currentPageState = { isMercadoLivre: false, isProductPage: false, url: '' };

function summarizeUrl(rawUrl) { if (!rawUrl) return ''; return rawUrl.length <= 72 ? rawUrl : `${rawUrl.slice(0, 69)}...`; }
function setStatusVariant(variant) { statusBoxElement.classList.remove('status-neutral', 'status-success', 'status-loading', 'status-error'); statusBoxElement.classList.add(variant); }
function setActionVisibility({ showSimulate, showCopy }) { simulateButton.hidden = !showSimulate; copyLinkButton.hidden = !showCopy; }

async function fetchJson(path, options = {}) {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });
  return response.json();
}

function renderStateFromPreview(preview, statusPayload, pageUrl) {
  currentPageState = { isMercadoLivre: preview.platform === 'mercadolivre', isProductPage: !!preview.is_product_page, url: pageUrl };
  const loginMessage = statusPayload?.logged_in ? `Conectado como ${statusPayload.user?.nome || statusPayload.user?.codigo_usuario}.` : 'Faça login no MinhaOferta para gerar links.';

  if (!preview.is_valid) {
    setStatusVariant('status-error'); statusElement.textContent = preview.message; detailsElement.textContent = 'Abra uma página de produto no Mercado Livre para usar a extensão.';
    noteElement.textContent = loginMessage; setActionVisibility({ showSimulate: false, showCopy: false });
  } else if (!preview.is_product_page) {
    setStatusVariant('status-neutral'); statusElement.textContent = preview.message; detailsElement.textContent = 'Mercado Livre detectado, mas não parece página de produto.';
    noteElement.textContent = loginMessage; setActionVisibility({ showSimulate: false, showCopy: false });
  } else {
    setStatusVariant('status-success'); statusElement.textContent = preview.message;
    detailsElement.textContent = `Estimativa inicial: ${preview.estimated_cashback_percent}% de cashback.`;
    noteElement.textContent = `${loginMessage} Geração real será conectada no próximo PR.`;
    setActionVisibility({ showSimulate: true, showCopy: false }); simulateButton.disabled = false; simulateButton.textContent = 'Gerar link com cashback';
  }
  urlElement.textContent = summarizeUrl(pageUrl || 'URL não disponível');
}

async function validateCurrentTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = activeTab?.url || '';

  try {
    const [statusPayload, preview] = await Promise.all([
      fetchJson('/api/extension/status'),
      fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify({ url }) })
    ]);
    renderStateFromPreview(preview, statusPayload, url);
  } catch (_) {
    setStatusVariant('status-error');
    statusElement.textContent = 'Não foi possível consultar o MinhaOferta agora.';
    detailsElement.textContent = 'Verifique sua conexão e tente novamente.';
    noteElement.textContent = 'O popup continua disponível mesmo sem backend.';
    setActionVisibility({ showSimulate: false, showCopy: false });
    urlElement.textContent = summarizeUrl(url || 'URL não disponível');
  }
}

function startSimulatedFlow() { if (!currentPageState.isMercadoLivre || !currentPageState.isProductPage) return; setStatusVariant('status-loading'); statusElement.textContent = 'Preparando seu link com cashback...'; detailsElement.textContent = 'Essa etapa ainda é uma simulação local da extensão.'; noteElement.textContent = ''; simulateButton.disabled = true; simulateButton.textContent = 'Preparando...'; setActionVisibility({ showSimulate: true, showCopy: false }); window.setTimeout(() => { setStatusVariant('status-success'); statusElement.textContent = 'Fluxo pronto para integração.'; detailsElement.textContent = 'No próximo PR, a extensão criará um job no backend.'; noteElement.textContent = 'Link simulado disponível apenas para validar UX.'; setActionVisibility({ showSimulate: false, showCopy: true }); }, SIMULATED_DELAY_MS); }

checkButton.addEventListener('click', () => { validateCurrentTab(); });
simulateButton.addEventListener('click', () => { startSimulatedFlow(); });
copyLinkButton.addEventListener('click', async () => { try { await navigator.clipboard.writeText(SIMULATED_LINK); copyLinkButton.textContent = 'Link simulado copiado'; window.setTimeout(() => { copyLinkButton.textContent = 'Copiar link simulado'; }, 1200); } catch (_) { noteElement.textContent = `Não foi possível copiar automaticamente. URL simulada: ${SIMULATED_LINK}`; } });
openSiteButton.addEventListener('click', () => { chrome.tabs.create({ url: 'https://minhaoferta.com' }); });
validateCurrentTab();
