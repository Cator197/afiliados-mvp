(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  let lastValidatedUrl = '';

  function classifyCurrentPage() {
    const result = {
      isMercadoLivre: false,
      isProductPage: false,
      reason: 'Página incompatível.'
    };

    const host = window.location.hostname;
    const path = window.location.pathname;
    const fullUrl = `${host}${path}${window.location.search}`;

    const isMercadoLivre = host === 'www.mercadolivre.com.br' || host === 'mercadolivre.com.br';

    if (!isMercadoLivre) {
      return { ...result, reason: 'Domínio diferente de Mercado Livre.' };
    }

    const hasProductPath = path.includes('/p/');
    const hasMlbPattern = /(?:\/|^)(MLB-\d+)/i.test(path) || /MLB-?\d+/i.test(fullUrl);

    const uiPdp = document.querySelector('.ui-pdp-container, .ui-pdp, [class*="ui-pdp"]');
    const productTitle = document.querySelector('h1.ui-pdp-title, h1[data-testid="header-title"], h1[class*="title"]');
    const productPrice = document.querySelector('[itemprop="price"], .andes-money-amount__fraction, [class*="price-tag"]');
    const buyAction = document.querySelector('[data-testid="action:buy-now"], .ui-pdp-actions, form[action*="/checkout"]');

    const domSignals = [uiPdp, productTitle, productPrice, buyAction].filter(Boolean).length;

    if (hasProductPath || hasMlbPattern || domSignals >= 3) {
      return {
        isMercadoLivre: true,
        isProductPage: true,
        reason: hasProductPath
          ? 'URL de produto com /p/.'
          : hasMlbPattern
            ? 'URL de produto com identificador MLB.'
            : 'Estrutura de produto detectada no DOM.'
      };
    }

    return {
      isMercadoLivre: true,
      isProductPage: false,
      reason: 'Mercado Livre detectado sem sinais suficientes de produto.'
    };
  }

  function createBanner() {
    const banner = document.createElement('aside');
    banner.id = BANNER_ID;
    banner.className = 'mo-banner';
    banner.setAttribute('role', 'complementary');
    banner.setAttribute('aria-label', 'Banner MinhaOferta');

    banner.innerHTML = `
      <button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button>
      <strong class="mo-banner-title">MinhaOferta</strong>
      <p class="mo-banner-text">Produto com cashback disponível.</p>
      <button type="button" class="mo-banner-action">Gerar em breve</button>
    `;

    const closeButton = banner.querySelector('.mo-banner-close');
    const actionButton = banner.querySelector('.mo-banner-action');

    closeButton?.addEventListener('click', () => {
      banner.remove();
    });

    actionButton?.addEventListener('click', () => {
      // Intencionalmente sem integração nesta fase (PR 3).
    });

    return banner;
  }

  function ensureBanner() {
    const existing = document.getElementById(BANNER_ID);
    if (existing) return;
    document.body.appendChild(createBanner());
  }

  function removeBanner() {
    document.getElementById(BANNER_ID)?.remove();
  }

  function validateAndRender() {
    const currentUrl = window.location.href;
    if (currentUrl === lastValidatedUrl && document.getElementById(BANNER_ID)) return;

    lastValidatedUrl = currentUrl;
    const classification = classifyCurrentPage();

    if (classification.isMercadoLivre && classification.isProductPage) {
      ensureBanner();
    } else {
      removeBanner();
    }
  }

  validateAndRender();
  window.setTimeout(validateAndRender, 1000);
  window.setTimeout(validateAndRender, 2000);

  let observerDebounce;
  const observer = new MutationObserver(() => {
    clearTimeout(observerDebounce);
    observerDebounce = window.setTimeout(() => {
      if (window.location.href !== lastValidatedUrl) {
        validateAndRender();
      }
    }, 400);
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('popstate', validateAndRender);
  window.addEventListener('hashchange', validateAndRender);
})();
