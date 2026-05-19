const statusElement = document.getElementById('status-text');
const urlElement = document.getElementById('current-url');
const checkButton = document.getElementById('check-page-btn');
const openSiteButton = document.getElementById('open-site-btn');

function isMercadoLivreUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    return parsed.hostname === 'mercadolivre.com.br' || parsed.hostname === 'www.mercadolivre.com.br';
  } catch (_) {
    return false;
  }
}

function summarizeUrl(rawUrl) {
  if (!rawUrl) return '';
  const maxLength = 72;
  if (rawUrl.length <= maxLength) return rawUrl;
  return `${rawUrl.slice(0, maxLength - 3)}...`;
}

function updateStatus(url) {
  const isCompatible = isMercadoLivreUrl(url);
  statusElement.textContent = isCompatible
    ? 'Página Mercado Livre detectada'
    : 'Esta página não é compatível';
  urlElement.textContent = summarizeUrl(url || 'URL não disponível');
}

async function validateCurrentTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  updateStatus(activeTab?.url || '');
}

checkButton.addEventListener('click', () => {
  validateCurrentTab();
});

openSiteButton.addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://minhaoferta.com' });
});

validateCurrentTab();
