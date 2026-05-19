(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  const BACKEND_BASE_URL = 'https://minhaoferta.com';
  const POLL_INTERVAL_MS = 2500;
  const POLL_MAX_ATTEMPTS = 20;
  let lastValidatedUrl = '';
  let previewRequestedForUrl = '';

  function classifyCurrentPage() {
    const host = window.location.hostname;
    const path = window.location.pathname;
    const fullUrl = `${host}${path}${window.location.search}`;
    const isMercadoLivre = host === 'www.mercadolivre.com.br' || host === 'mercadolivre.com.br';
    if (!isMercadoLivre) return { isMercadoLivre: false, isProductPage: false };
    const hasProductPath = path.includes('/p/');
    const hasMlbPattern = /(?:\/|^)(MLB-\d+)/i.test(path) || /MLB-?\d+/i.test(fullUrl);
    return { isMercadoLivre: true, isProductPage: hasProductPath || hasMlbPattern };
  }

  function parsePriceCandidate(value) {
    if (value == null) return null;
    const raw = String(value).trim();
    if (!raw) return null;
    const cleaned = raw.replace(/R\$/gi, '').replace(/\s+/g, '');
    const hasComma = cleaned.includes(',');
    const hasDot = cleaned.includes('.');
    let normalized = cleaned;
    if (hasComma && hasDot) normalized = cleaned.replace(/\./g, '').replace(',', '.');
    else if (hasComma) normalized = cleaned.replace(',', '.');
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 1000000) return null;
    return parsed;
  }

  function detectPriceFromPage() {
    const candidates = [];
    const metaPrice = document.querySelector('meta[itemprop="price"]')?.getAttribute('content');
    if (metaPrice) candidates.push(metaPrice);

    const andesAmount = document.querySelector('[data-andes-money-amount]')?.getAttribute('data-andes-money-amount');
    if (andesAmount) candidates.push(andesAmount);

    const selectors = [
      '.andes-money-amount__fraction',
      '.ui-pdp-price__second-line .andes-money-amount__fraction',
      '.ui-pdp-price__part',
      '.price-tag-fraction'
    ];
    selectors.forEach((selector) => {
      const text = document.querySelector(selector)?.textContent;
      if (text) candidates.push(text);
    });

    for (const candidate of candidates) {
      const price = parsePriceCandidate(candidate);
      if (price) return price;
    }
    return null;
  }

  async function fetchJson(path, options = {}) {
    const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    });
    return { status: response.status, body: await response.json() };
  }

  async function pollJob(jobId) { /* unchanged */
    for (let i = 0; i < POLL_MAX_ATTEMPTS; i += 1) {
      const { body } = await fetchJson(`/api/extension/jobs/${jobId}`);
      if (body.status === 'success' && body.affiliate_url) return body.affiliate_url;
      if (body.status === 'error') throw new Error('error');
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    throw new Error('timeout');
  }

  function setBannerState(banner, state, extra) {
    const text = banner.querySelector('.mo-banner-text');
    const subtext = banner.querySelector('.mo-banner-subtext');
    const actions = banner.querySelector('.mo-banner-actions');
    if (state === 'loading') { text.textContent = 'Gerando seu link...'; subtext.textContent = 'Seu pedido está em processamento.'; actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary mo-btn-disabled" disabled>Gerando...</button>'; return; }
    if (state === 'done') { text.textContent = 'Link gerado com sucesso.'; subtext.textContent = extra || ''; actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="copy">Copiar link</button>'; actions.querySelector('[data-action="copy"]')?.addEventListener('click', async () => navigator.clipboard.writeText(extra || '')); return; }
    if (state === 'error') { text.textContent = extra || 'Não foi possível conectar ao MinhaOferta agora.'; subtext.textContent = ''; actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="open-site">Entrar no MinhaOferta</button>'; actions.querySelector('[data-action="open-site"]')?.addEventListener('click', () => window.open('https://minhaoferta.com', '_blank', 'noopener,noreferrer')); return; }
    text.textContent = extra || 'Cashback disponível neste produto.';
    subtext.textContent = 'Gere seu link antes de comprar para participar do cashback.';
    actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="generate">Gerar link com cashback</button>';
    actions.querySelector('[data-action="generate"]')?.addEventListener('click', async () => {
      setBannerState(banner, 'loading');
      try {
        const { status, body } = await fetchJson('/api/extension/generate-link', { method: 'POST', body: JSON.stringify({ url: window.location.href }) });
        if (status === 401 || body.error === 'login_required') return setBannerState(banner, 'error', 'Entre no MinhaOferta para gerar seu link com cashback.');
        if (body.error === 'invalid_url') return setBannerState(banner, 'error', 'Esta página não é compatível.');
        if (body.error === 'not_product_page') return setBannerState(banner, 'error', 'Acesse uma página de produto do Mercado Livre.');
        const affiliateUrl = await pollJob(body.job_id);
        setBannerState(banner, 'done', affiliateUrl);
      } catch (err) {
        setBannerState(banner, 'error', err?.message === 'timeout' ? 'Seu link ainda está em processamento. Veja no histórico.' : 'Não foi possível conectar ao MinhaOferta agora.');
      }
    });
  }

  function createBanner() { const banner = document.createElement('aside'); banner.id = BANNER_ID; banner.className = 'mo-banner is-default'; banner.innerHTML = '<button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button><strong class="mo-banner-title">MinhaOferta</strong><p class="mo-banner-text"></p><p class="mo-banner-subtext"></p><div class="mo-banner-actions"></div>'; banner.querySelector('.mo-banner-close')?.addEventListener('click', () => banner.remove()); setBannerState(banner, 'default'); return banner; }
  function ensureBanner() { if (!document.getElementById(BANNER_ID)) document.body.appendChild(createBanner()); }
  function removeBanner() { document.getElementById(BANNER_ID)?.remove(); }

  async function updateBannerPreview() {
    const banner = document.getElementById(BANNER_ID);
    if (!banner || previewRequestedForUrl === window.location.href) return;
    previewRequestedForUrl = window.location.href;
    try {
      const payload = { url: window.location.href, price: detectPriceFromPage() };
      const { body } = await fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify(payload) });
      setBannerState(banner, 'default', body?.estimated_cashback_label || 'Cashback disponível neste produto.');
    } catch (_) {
      setBannerState(banner, 'default', 'Cashback disponível neste produto.');
    }
  }

  function validateAndRender() { if (window.location.href === lastValidatedUrl && document.getElementById(BANNER_ID)) return; lastValidatedUrl = window.location.href; previewRequestedForUrl = ''; const c = classifyCurrentPage(); if (c.isMercadoLivre && c.isProductPage) { ensureBanner(); updateBannerPreview(); } else removeBanner(); }
  validateAndRender(); window.setTimeout(validateAndRender, 1000); window.setTimeout(validateAndRender, 2000);
})();
