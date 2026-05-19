(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  const BACKEND_BASE_URL = 'https://minhaoferta.com';
  const POLL_INTERVAL_MS = 2500;
  const POLL_MAX_ATTEMPTS = 20;
  let lastValidatedUrl = '';

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

  async function fetchJson(path, options = {}) {
    const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    });
    return { status: response.status, body: await response.json() };
  }

  async function pollJob(jobId) {
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
    if (state === 'loading') {
      text.textContent = 'Gerando seu link...'; subtext.textContent = 'Seu pedido está em processamento.';
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary mo-btn-disabled" disabled>Gerando...</button>'; return;
    }
    if (state === 'done') {
      text.textContent = 'Link gerado com sucesso.'; subtext.textContent = extra || '';
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="copy">Copiar link</button>';
      actions.querySelector('[data-action="copy"]')?.addEventListener('click', async () => navigator.clipboard.writeText(extra || ''));
      return;
    }
    if (state === 'error') {
      text.textContent = extra || 'Não foi possível conectar ao MinhaOferta agora.'; subtext.textContent = '';
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="open-site">Entrar no MinhaOferta</button>';
      actions.querySelector('[data-action="open-site"]')?.addEventListener('click', () => window.open('https://minhaoferta.com', '_blank', 'noopener,noreferrer'));
      return;
    }
    text.textContent = 'Produto com cashback disponível.';
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

  function createBanner() {
    const banner = document.createElement('aside'); banner.id = BANNER_ID; banner.className = 'mo-banner is-default';
    banner.innerHTML = '<button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button><strong class="mo-banner-title">MinhaOferta</strong><p class="mo-banner-text"></p><p class="mo-banner-subtext"></p><div class="mo-banner-actions"></div>';
    banner.querySelector('.mo-banner-close')?.addEventListener('click', () => banner.remove()); setBannerState(banner, 'default'); return banner;
  }
  function ensureBanner() { if (!document.getElementById(BANNER_ID)) document.body.appendChild(createBanner()); }
  function removeBanner() { document.getElementById(BANNER_ID)?.remove(); }
  function validateAndRender() { if (window.location.href === lastValidatedUrl && document.getElementById(BANNER_ID)) return; lastValidatedUrl = window.location.href; const c = classifyCurrentPage(); if (c.isMercadoLivre && c.isProductPage) ensureBanner(); else removeBanner(); }
  validateAndRender(); window.setTimeout(validateAndRender, 1000); window.setTimeout(validateAndRender, 2000);
})();
