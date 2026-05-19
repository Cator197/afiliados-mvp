(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  const SIMULATED_DELAY_MS = 1400;
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

  function setBannerState(banner, state) {
    const title = banner.querySelector('.mo-banner-title');
    const text = banner.querySelector('.mo-banner-text');
    const subtext = banner.querySelector('.mo-banner-subtext');
    const actions = banner.querySelector('.mo-banner-actions');

    banner.classList.remove('is-default', 'is-loading', 'is-success');

    if (state === 'loading') {
      banner.classList.add('is-loading');
      title.textContent = 'MinhaOferta';
      text.textContent = 'Preparando seu link com cashback...';
      subtext.textContent = 'Essa etapa ainda é uma simulação local da extensão.';
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary mo-btn-disabled" disabled>Preparando...</button>';
      return;
    }

    if (state === 'success') {
      banner.classList.add('is-success');
      title.textContent = 'MinhaOferta';
      text.textContent = 'Fluxo da extensão pronto.';
      subtext.textContent = 'No próximo PR, este botão será conectado ao backend do MinhaOferta.';
      actions.innerHTML = `
        <button type="button" class="mo-btn mo-btn-primary" data-action="open-site">Abrir MinhaOferta</button>
        <button type="button" class="mo-btn mo-btn-secondary" data-action="close-banner">Fechar</button>
      `;
      actions.querySelector('[data-action="open-site"]')?.addEventListener('click', () => {
        window.open('https://minhaoferta.com', '_blank', 'noopener,noreferrer');
      });
      actions.querySelector('[data-action="close-banner"]')?.addEventListener('click', () => {
        banner.remove();
      });
      return;
    }

    banner.classList.add('is-default');
    title.textContent = 'MinhaOferta';
    text.textContent = 'Produto com cashback disponível.';
    subtext.textContent = 'Gere seu link antes de comprar para participar do cashback.';
    actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="simulate">Gerar link com cashback</button>';
    actions.querySelector('[data-action="simulate"]')?.addEventListener('click', () => {
      setBannerState(banner, 'loading');
      window.setTimeout(() => {
        setBannerState(banner, 'success');
      }, SIMULATED_DELAY_MS);
    });
  }

  function createBanner() {
    const banner = document.createElement('aside');
    banner.id = BANNER_ID;
    banner.className = 'mo-banner is-default';
    banner.setAttribute('role', 'complementary');
    banner.setAttribute('aria-label', 'Banner MinhaOferta');

    banner.innerHTML = `
      <button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button>
      <strong class="mo-banner-title"></strong>
      <p class="mo-banner-text"></p>
      <p class="mo-banner-subtext"></p>
      <div class="mo-banner-actions"></div>
    `;

    banner.querySelector('.mo-banner-close')?.addEventListener('click', () => {
      banner.remove();
    });

    setBannerState(banner, 'default');
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
