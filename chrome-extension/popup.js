const statusElement = document.getElementById('status-text');
const detailsElement = document.getElementById('status-details');
const urlElement = document.getElementById('current-url');
const checkButton = document.getElementById('check-page-btn');
const openSiteButton = document.getElementById('open-site-btn');

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

    if (hasProductPath) {
      return {
        isMercadoLivre: true,
        isProductPage: true,
        reason: 'URL com padrão /p/ de produto.'
      };
    }

    if (hasMlbPattern) {
      return {
        isMercadoLivre: true,
        isProductPage: true,
        reason: 'URL com identificador MLB de produto.'
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

function updateStatus(url) {
  const page = classifyMercadoLivrePage(url);

  if (!page.isMercadoLivre) {
    statusElement.textContent = 'Esta página não é compatível.';
    detailsElement.textContent = 'Acesse uma página de produto para gerar um link com cashback.';
  } else if (!page.isProductPage) {
    statusElement.textContent = 'Você está no Mercado Livre, mas esta página não parece ser um produto.';
    detailsElement.textContent = 'Acesse uma página de produto para gerar um link com cashback.';
  } else {
    statusElement.textContent = 'Produto Mercado Livre detectado.';
    detailsElement.textContent = 'Em breve você poderá gerar seu link com cashback por aqui.';
  }

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
