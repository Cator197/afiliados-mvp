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

  function getCurrentProductUrl() {
    return normalizeUrl(window.location.href);
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
    const body = await response.json();
    return { status: response.status, body };
  }

  async function checkExtensionLogin() {
    const { status, body } = await fetchJson('/api/extension/status');
    return status === 200 && Boolean(body?.logged_in);
  }

  async function requestGenerateLink(url) {
    const { status, body } = await fetchJson('/api/extension/generate-link', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
    if (status === 401 || body?.error === 'login_required') {
      const err = new Error('login_required');
      err.code = 'login_required';
      throw err;
    }
    if (status >= 400 || !body?.job_id) {
      const err = new Error('generate_failed');
      err.code = 'generate_failed';
      throw err;
    }
    return body.job_id;
  }

  async function pollExtensionJob(jobId) {
    for (let i = 0; i < POLL_MAX_ATTEMPTS; i += 1) {
      const { status, body } = await fetchJson(`/api/extension/jobs/${jobId}`);
      if (status >= 400) throw new Error('job_failed');
      if (body?.status === 'success' && body?.affiliate_url) return body.affiliate_url;
      if (body?.status === 'error') throw new Error('job_failed');
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    throw new Error('timeout');
  }

  function openUrl(url) {
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  function removeBanner() { document.getElementById(BANNER_ID)?.remove(); }

  function setBannerState(state, data = {}) {
    const banner = document.getElementById(BANNER_ID);
    if (!banner) return;
    const title = banner.querySelector('.mo-banner-title');
    const text = banner.querySelector('.mo-banner-text');
    const subtext = banner.querySelector('.mo-banner-subtext');
    const actions = banner.querySelector('.mo-banner-actions');

    banner.classList.remove('is-loading', 'is-success');
    title.textContent = data.title || (state === 'initial' ? 'Cashback MinhaOferta' : 'MinhaOferta');
    text.textContent = data.text || '';
    subtext.textContent = data.subtext || '';
    subtext.style.display = data.subtext ? 'block' : 'none';
    actions.innerHTML = '';

    if (state === 'loading') {
      banner.classList.add('is-loading');
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" disabled>Gerando link...</button>';
      return;
    }

    if (state === 'success') {
      banner.classList.add('is-success');
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="open-link">Abrir link</button>';
      actions.querySelector('[data-action="open-link"]')?.addEventListener('click', () => openUrl(currentAffiliateUrl));
      return;
    }

    if (state === 'login-required') {
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="login">Entrar</button>';
      actions.querySelector('[data-action="login"]')?.addEventListener('click', () => openUrl(BACKEND_BASE_URL));
      return;
    }

    if (state === 'timeout') {
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-secondary" data-action="open-main">Abrir MinhaOferta</button>';
      actions.querySelector('[data-action="open-main"]')?.addEventListener('click', () => openUrl(BACKEND_BASE_URL));
      return;
    }

    const label = state === 'error' ? 'Tentar novamente' : 'Gerar link';
    actions.innerHTML = `<button type="button" class="mo-btn mo-btn-primary" data-action="generate">${label}</button>`;
    actions.querySelector('[data-action="generate"]')?.addEventListener('click', handleGenerateClick);
  }

  async function handleGenerateClick() {
    if (isGenerating) return;
    isGenerating = true;
    setBannerState('loading', {
      text: 'Gerando seu link com cashback...',
      subtext: 'Isso pode levar alguns segundos.',
    });

    try {
      const loggedIn = await checkExtensionLogin();
      if (!loggedIn) {
        setBannerState('login-required', {
          text: 'Entre no MinhaOferta para gerar seu link com cashback.',
        });
        return;
      }

      const jobId = await requestGenerateLink(getCurrentProductUrl());
      currentAffiliateUrl = await pollExtensionJob(jobId);
      setBannerState('success', {
        text: 'Link com cashback gerado.',
      });
    } catch (err) {
      if (err?.code === 'login_required') {
        setBannerState('login-required', { text: 'Entre no MinhaOferta para gerar seu link com cashback.' });
      } else if (err?.message === 'timeout') {
        setBannerState('timeout', {
          text: 'Seu link ainda está sendo processado.',
          subtext: 'Acompanhe pelo histórico no MinhaOferta.',
        });
      } else {
        console.warn('[MinhaOferta] Falha ao gerar link pelo banner.', err);
        setBannerState('error', {
          text: 'Não foi possível gerar o link agora.',
        });
      }
    } finally {
      isGenerating = false;
    }
  }

  function createBanner() {
    const banner = document.createElement('aside');
    banner.id = BANNER_ID;
    banner.className = 'mo-banner';
    banner.innerHTML = '<button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button><strong class="mo-banner-title"></strong><p class="mo-banner-text"></p><p class="mo-banner-subtext"></p><div class="mo-banner-actions"></div>';
    banner.querySelector('.mo-banner-close')?.addEventListener('click', async () => { await rememberBannerClosed(window.location.href); banner.remove(); });
    setBannerState('initial', {
      text: 'Cashback disponível neste produto.',
      subtext: 'Gere seu link antes de comprar.',
    });
    return banner;
  }

  async function updateBannerPreview() {
    const currentUrl = getCurrentProductUrl();
    if (previewRequestedForUrl === currentUrl) return;
    previewRequestedForUrl = currentUrl;
    try {
      const { body } = await fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify({ url: currentUrl }) });
      if (body?.estimated_cashback_label) {
        setBannerState('initial', {
          text: `Cashback estimado de até ${body.estimated_cashback_label}`,
          subtext: 'Gere seu link antes de comprar.',
        });
      }
    } catch (err) {
      console.error('[MinhaOferta] Falha ao carregar preview do banner.', err);
    }
  }

  async function validateAndRender(force = false) {
    const currentUrl = getCurrentProductUrl();
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
