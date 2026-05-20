(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  const BACKEND_BASE_URL = 'https://minhaoferta.com';
  const DISMISS_TTL_MS = 24 * 60 * 60 * 1000;
  const CHECK_URL_INTERVAL_MS = 1200;
  const POLL_INTERVAL_MS = 2500;
  const POLL_MAX_ATTEMPTS = 20;
  let lastUrl = '';
  let previewRequestedForUrl = '';
  let isGenerating = false;
  let currentAffiliateUrl = '';

  const normalizeUrl = (u) => (u || '').split('#')[0];
  const keyForUrl = (u) => `mo_banner_closed_${normalizeUrl(u)}`;
  const isMercadoLivreHost = (h) => h === 'www.mercadolivre.com.br' || h === 'mercadolivre.com.br';

  function classifyCurrentPage() {
    const host = window.location.hostname;
    const path = window.location.pathname;
    const fullUrl = `${host}${path}${window.location.search}`;
    if (!isMercadoLivreHost(host)) return { isMercadoLivre: false, isProductPage: false };
    const hasProductPath = path.includes('/p/');
    const hasMlbPattern = /(?:\/|^)(MLB-\d+)/i.test(path) || /MLB-?\d+/i.test(fullUrl);
    return { isMercadoLivre: true, isProductPage: hasProductPath || hasMlbPattern };
  }

  async function wasBannerClosedRecently(url) {
    const key = keyForUrl(url);
    const res = await chrome.storage.local.get([key]);
    const ts = Number(res[key] || 0);
    return ts > 0 && Date.now() - ts < DISMISS_TTL_MS;
  }

  async function rememberBannerClosed(url) {
    const key = keyForUrl(url);
    const cleanupBefore = Date.now() - (DISMISS_TTL_MS * 3);
    const all = await chrome.storage.local.get(null);
    const toRemove = [];
    Object.keys(all).forEach((k) => { if (k.startsWith('mo_banner_closed_') && Number(all[k] || 0) < cleanupBefore) toRemove.push(k); });
    if (toRemove.length) await chrome.storage.local.remove(toRemove);
    await chrome.storage.local.set({ [key]: Date.now() });
  }

  async function fetchJson(path, options = {}) {
    const response = await fetch(`${BACKEND_BASE_URL}${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...options });
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



  function extractBreadcrumbContext() {
    const selector = '#breadcrumb a.andes-breadcrumb__link, a.andes-breadcrumb__link';
    const links = Array.from(document.querySelectorAll(selector));
    const items = links
      .map((link) => {
        const text = (link.textContent || '').trim();
        const title = (link.getAttribute('title') || '').trim();
        const href = (link.getAttribute('href') || '').trim();
        if (!text && !title && !href) return null;
        let pathname = '';
        try { pathname = href ? new URL(href, window.location.origin).pathname : ''; } catch (_) { pathname = ''; }
        return { text, title, href, pathname };
      })
      .filter(Boolean);

    const normalized = items.filter((item) => {
      const label = (item.text || item.title || '').trim().toLowerCase();
      return label && label !== 'voltar';
    });

    const category = normalized[0] || null;
    return {
      category_hint: category ? (category.text || category.title || '') : null,
      category_path: category ? category.pathname || null : null,
      breadcrumbs: normalized.map((item) => item.text || item.title || '').filter(Boolean),
      breadcrumb_paths: normalized.map((item) => item.pathname || '').filter(Boolean),
    };
  }

  function removeBanner() { document.getElementById(BANNER_ID)?.remove(); }

  function setBannerState(banner, state, text = '', subtext = '') {
    const t = banner.querySelector('.mo-banner-text');
    const s = banner.querySelector('.mo-banner-subtext');
    const actions = banner.querySelector('.mo-banner-actions');
    t.textContent = text;
    s.textContent = subtext;

    if (state === 'loading') {
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" disabled>Gerando...</button>';
      return;
    }
    if (state === 'done') {
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="copy">Copiar link</button><button type="button" class="mo-btn mo-btn-secondary" data-action="open">Abrir link</button><button type="button" class="mo-btn mo-btn-secondary" data-action="history">Ver histórico</button>';
      actions.querySelector('[data-action="copy"]')?.addEventListener('click', ()=> navigator.clipboard.writeText(currentAffiliateUrl));
      actions.querySelector('[data-action="open"]')?.addEventListener('click', ()=> window.open(currentAffiliateUrl, '_blank', 'noopener,noreferrer'));
      actions.querySelector('[data-action="history"]')?.addEventListener('click', ()=> window.open(`${BACKEND_BASE_URL}/historico`, '_blank', 'noopener,noreferrer'));
      return;
    }

    actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="generate">Gerar link com cashback</button>';
    const btn = actions.querySelector('[data-action="generate"]');
    btn?.addEventListener('click', async () => {
      if (isGenerating) return;
      isGenerating = true;
      setBannerState(banner, 'loading', 'Gerando seu link com cashback...', 'Isso pode levar alguns segundos.');
      try {
        const { status, body } = await fetchJson('/api/extension/generate-link', { method: 'POST', body: JSON.stringify({ url: window.location.href, ...extractBreadcrumbContext() }) });
        if (status === 401 || body.error === 'login_required') {
          setBannerState(banner, 'default', 'Entre no MinhaOferta para gerar seu link com cashback.', '', true);
        } else {
          const affiliateUrl = await pollJob(body.job_id);
          currentAffiliateUrl = affiliateUrl;
          setBannerState(banner, 'done', 'Link gerado com sucesso.', '');
        }
      } catch (err) {
        const timeout = err?.message === 'timeout';
        setBannerState(banner, 'default', timeout ? 'Seu link ainda está sendo processado.' : 'Não foi possível conectar ao MinhaOferta agora.', timeout ? 'Você pode acompanhar pelo histórico.' : 'Verifique sua conexão e tente novamente.');
      } finally { isGenerating = false; }
    });
  }

  function createBanner() {
    const banner = document.createElement('aside');
    banner.id = BANNER_ID;
    banner.className = 'mo-banner';
    banner.innerHTML = '<button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button><strong class="mo-banner-title">MinhaOferta</strong><p class="mo-banner-text"></p><p class="mo-banner-subtext"></p><div class="mo-banner-actions"></div>';
    banner.querySelector('.mo-banner-close')?.addEventListener('click', async () => { await rememberBannerClosed(window.location.href); banner.remove(); });
    setBannerState(banner, 'default', 'Produto com cashback disponível.', 'Gere seu link antes de comprar para participar do cashback.');
    return banner;
  }

  async function updateBannerPreview() {
    const banner = document.getElementById(BANNER_ID);
    const currentUrl = normalizeUrl(window.location.href);
    if (!banner || previewRequestedForUrl === currentUrl) return;
    previewRequestedForUrl = currentUrl;
    try {
      const { body } = await fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify({ url: currentUrl, ...extractBreadcrumbContext() }) });
      if (body?.estimated_cashback_label) {
        setBannerState(banner, 'default', body.estimated_cashback_label, 'Valor estimado. O cashback final depende da confirmação da compra.');
      }
    } catch (_) {}
  }

  async function validateAndRender(force = false) {
    const currentUrl = normalizeUrl(window.location.href);
    if (!force && currentUrl === lastUrl) return;
    lastUrl = currentUrl;
    previewRequestedForUrl = '';
    removeBanner();
    const c = classifyCurrentPage();
    if (!c.isMercadoLivre || !c.isProductPage) return;
    if (await wasBannerClosedRecently(currentUrl)) return;
    document.body.appendChild(createBanner());
    updateBannerPreview();
  }

  const rawPush = history.pushState;
  history.pushState = function (...args) { rawPush.apply(this, args); setTimeout(() => validateAndRender(true), 250); };
  const rawReplace = history.replaceState;
  history.replaceState = function (...args) { rawReplace.apply(this, args); setTimeout(() => validateAndRender(true), 250); };
  window.addEventListener('popstate', () => setTimeout(() => validateAndRender(true), 250));
  setInterval(() => validateAndRender(false), CHECK_URL_INTERVAL_MS);
  validateAndRender(true);
})();
