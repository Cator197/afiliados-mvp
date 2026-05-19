const statusBoxElement = document.getElementById('popup-status-box');
const statusElement = document.getElementById('status-text');
const detailsElement = document.getElementById('status-details');
const noteElement = document.getElementById('status-note');
const urlElement = document.getElementById('current-url');
const simulateButton = document.getElementById('simulate-btn');
const copyLinkButton = document.getElementById('copy-link-btn');
const checkButton = document.getElementById('check-page-btn');
const openSiteButton = document.getElementById('open-site-btn');

const SIMULATED_DELAY_MS = 1400;
const SIMULATED_LINK = 'https://minhaoferta.com/link-simulado';

let currentPageState = {
  isMercadoLivre: false,
  isProductPage: false,
  url: ''
};

function classifyMercadoLivrePage(rawUrl) {
  const result = {
    isMercadoLivre: false,
    isProductPage: false,
    reason: 'URL inválida ou indisponível.'
  };

  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname;
    const fullUrl = `${parsed.hostname}${parsed.pathname}${parsed.search}`;
    const path = parsed.pathname;

    const isMercadoLivre = host === 'mercadolivre.com.br' || host === 'www.mercadolivre.com.br';

    if (!isMercadoLivre) {
      return { ...result, reason: 'Domínio diferente de Mercado Livre.' };
    }

    const hasProductPath = path.includes('/p/');
    const hasMlbPattern = /(?:\/|^)(MLB-\d+)/i.test(path) || /MLB-?\d+/i.test(fullUrl);

    if (hasProductPath || hasMlbPattern) {
      return {
        isMercadoLivre: true,
        isProductPage: true,
        reason: 'Página de produto detectada pela URL.'
      };
    }

    return {
      isMercadoLivre: true,
      isProductPage: false,
      reason: 'Mercado Livre detectado, sem padrão confiável de produto na URL.'
    };
  } catch (_) {
    return result;
  }
}

function summarizeUrl(rawUrl) {
  if (!rawUrl) return '';
  const maxLength = 72;
  if (rawUrl.length <= maxLength) return rawUrl;
  return `${rawUrl.slice(0, maxLength - 3)}...`;
}

function setStatusVariant(variant) {
  statusBoxElement.classList.remove('status-neutral', 'status-success', 'status-loading', 'status-error');
  statusBoxElement.classList.add(variant);
}

function setActionVisibility({ showSimulate, showCopy }) {
  simulateButton.hidden = !showSimulate;
  copyLinkButton.hidden = !showCopy;
}

function renderDetectedState(page) {
  currentPageState = { ...page };

  if (!page.isMercadoLivre) {
    setStatusVariant('status-error');
    statusElement.textContent = 'Esta página não é compatível.';
    detailsElement.textContent = 'Abra uma página de produto no Mercado Livre para usar a extensão.';
    noteElement.textContent = '';
    setActionVisibility({ showSimulate: false, showCopy: false });
  } else if (!page.isProductPage) {
    setStatusVariant('status-neutral');
    statusElement.textContent = 'Você está no Mercado Livre, mas esta página não parece ser um produto.';
    detailsElement.textContent = 'Acesse um produto para liberar a geração do link com cashback.';
    noteElement.textContent = '';
    setActionVisibility({ showSimulate: false, showCopy: false });
  } else {
    setStatusVariant('status-success');
    statusElement.textContent = 'Produto detectado';
    detailsElement.textContent = 'Este produto poderá gerar cashback pelo MinhaOferta.';
    noteElement.textContent = 'Produto Mercado Livre detectado.';
    setActionVisibility({ showSimulate: true, showCopy: false });
    simulateButton.disabled = false;
    simulateButton.textContent = 'Gerar link com cashback';
  }

  urlElement.textContent = summarizeUrl(page.url || 'URL não disponível');
}

async function validateCurrentTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = activeTab?.url || '';
  const page = classifyMercadoLivrePage(url);
  renderDetectedState({ ...page, url });
}

function startSimulatedFlow() {
  if (!currentPageState.isMercadoLivre || !currentPageState.isProductPage) return;

  setStatusVariant('status-loading');
  statusElement.textContent = 'Preparando seu link com cashback...';
  detailsElement.textContent = 'Essa etapa ainda é uma simulação local da extensão.';
  noteElement.textContent = '';
  simulateButton.disabled = true;
  simulateButton.textContent = 'Preparando...';
  setActionVisibility({ showSimulate: true, showCopy: false });

  window.setTimeout(() => {
    setStatusVariant('status-success');
    statusElement.textContent = 'Fluxo pronto para integração.';
    detailsElement.textContent = 'No próximo PR, a extensão criará um job no backend.';
    noteElement.textContent = 'Link simulado disponível apenas para validar UX.';
    setActionVisibility({ showSimulate: false, showCopy: true });
  }, SIMULATED_DELAY_MS);
}

checkButton.addEventListener('click', () => {
  validateCurrentTab();
});

simulateButton.addEventListener('click', () => {
  startSimulatedFlow();
});

copyLinkButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(SIMULATED_LINK);
    copyLinkButton.textContent = 'Link simulado copiado';
    window.setTimeout(() => {
      copyLinkButton.textContent = 'Copiar link simulado';
    }, 1200);
  } catch (_) {
    noteElement.textContent = `Não foi possível copiar automaticamente. URL simulada: ${SIMULATED_LINK}`;
  }
});

openSiteButton.addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://minhaoferta.com' });
});

validateCurrentTab();
