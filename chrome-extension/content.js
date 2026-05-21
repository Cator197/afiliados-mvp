(function initMinhaOfertaBanner() {
  const BANNER_ID = 'mo-cashback-banner';
  const BACKEND_BASE_URL = 'https://minhaoferta.com';
  const DISMISS_TTL_MS = 24 * 60 * 60 * 1000;
  const CHECK_URL_INTERVAL_MS = 1200;
  const POLL_INTERVAL_MS = 3000;
  const GENERATED_LINKS_STORAGE_KEY = 'generatedLinks';
  const GENERATED_LINK_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const POLL_MAX_ATTEMPTS = 20;
  let lastUrl = '';
  let previewRequestedForUrl = '';
  let isGenerating = false;
  let currentAffiliateUrl = '';

  const normalizeUrl = (u) => (u || '').split('#')[0];

  function normalizeProductUrl(inputUrl) {
    try {
      const parsed = new URL(inputUrl);
      parsed.hash = '';
      parsed.search = '';
      return `${parsed.origin}${parsed.pathname.replace(/\/+$/, '')}`;
    } catch {
      return inputUrl || '';
    }
  }

  function isGeneratedLinkExpired(entry) {
    const createdAt = Number(entry?.created_at || 0);
    return !createdAt || (Date.now() - createdAt) > GENERATED_LINK_TTL_MS;
  }

  async function cleanupExpiredGeneratedLinks() {
    const store = await chrome.storage.local.get([GENERATED_LINKS_STORAGE_KEY]);
    const links = store[GENERATED_LINKS_STORAGE_KEY] || {};
    const cleanedEntries = {};
    Object.entries(links).forEach(([key, value]) => {
      if (!isGeneratedLinkExpired(value)) cleanedEntries[key] = value;
    });
    if (Object.keys(cleanedEntries).length !== Object.keys(links).length) {
      await chrome.storage.local.set({ [GENERATED_LINKS_STORAGE_KEY]: cleanedEntries });
    }
  }

  async function getStoredGeneratedLinkForUrl(url) {
    const normalizedUrl = normalizeProductUrl(url);
    const store = await chrome.storage.local.get([GENERATED_LINKS_STORAGE_KEY]);
    const links = store[GENERATED_LINKS_STORAGE_KEY] || {};
    const entry = links[normalizedUrl];
    if (!entry) return null;
    if (isGeneratedLinkExpired(entry)) {
      delete links[normalizedUrl];
      await chrome.storage.local.set({ [GENERATED_LINKS_STORAGE_KEY]: links });
      return null;
    }
    return entry;
  }

  async function saveGeneratedLink(url, payload) {
    const normalizedUrl = normalizeProductUrl(url);
    const store = await chrome.storage.local.get([GENERATED_LINKS_STORAGE_KEY]);
    const links = store[GENERATED_LINKS_STORAGE_KEY] || {};
    links[normalizedUrl] = {
      affiliate_url: payload.affiliate_url,
      job_id: payload.job_id,
      created_at: Date.now(),
      source: 'extension',
      original_url: url,
      estimated_cashback_label: payload.estimated_cashback_label || '',
      category_name: payload.category_name || ''
    };
    await chrome.storage.local.set({ [GENERATED_LINKS_STORAGE_KEY]: links });
  }
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
    let body = null;
    try { body = await response.json(); } catch { body = null; }
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
      if (status === 401) throw new Error('login_required');
      if (status === 403) throw new Error('job_failed');
      if (status === 404) throw new Error('job_not_found');
      if (status >= 500) throw new Error('job_failed');
      if (!body) throw new Error('job_failed');
      if (body?.status === 'success' && body?.affiliate_url) return body.affiliate_url;
      if (body?.status === 'success' && !body?.affiliate_url) throw new Error('job_failed');
      if (body?.status === 'error') throw new Error('job_failed');
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    throw new Error('timeout');
  }

  function isHttpUrl(url) {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }

  function openUrl(url) {
    if (!isHttpUrl(url)) return false;
    window.open(url, '_blank', 'noopener,noreferrer');
    return true;
  }

  function removeBanner() { document.getElementById(BANNER_ID)?.remove(); }

  function setBannerState(state, data = {}) {
    const banner = document.getElementById(BANNER_ID);
    if (!banner) return;
    const title = banner.querySelector('.mo-banner-title');
    const highlight = banner.querySelector('.mo-banner-highlight');
    const subtext = banner.querySelector('.mo-banner-subtext');
    const actions = banner.querySelector('.mo-banner-actions');

    banner.classList.remove('is-loading', 'is-success', 'is-error');
    title.textContent = data.title || 'MinhaOferta';
    highlight.textContent = data.text || '';
    subtext.textContent = data.subtext || '';
    subtext.style.display = data.subtext ? 'block' : 'none';
    actions.innerHTML = '';

    if (state === 'loading') {
      banner.classList.add('is-loading');
      actions.innerHTML = '<div class="mo-loading" aria-live="polite"><span class="mo-spinner" aria-hidden="true"></span><span class="mo-loading-label">Aguarde</span></div>';
      return;
    }

    if (state === 'success') {
      banner.classList.add('is-success');
      actions.innerHTML = '<button type="button" class="mo-btn mo-btn-primary" data-action="open-link">Abrir link</button>';
      actions.querySelector('[data-action="open-link"]')?.addEventListener('click', () => {
        if (!openUrl(currentAffiliateUrl)) {
          setBannerState('error', {
            title: 'MinhaOferta',
            text: 'Não foi possível abrir o link gerado.',
            subtext: ''
          });
        }
      });
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

    if (state === 'error') banner.classList.add('is-error');

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
          subtext: '',
        });
        return;
      }

      const productUrl = getCurrentProductUrl();
      const existing = await getStoredGeneratedLinkForUrl(productUrl);
      if (existing?.affiliate_url) {
        currentAffiliateUrl = existing.affiliate_url;
        setBannerState('success', {
          title: 'Link de cashback pronto',
          text: 'Link de cashback pronto',
          subtext: 'Você já tem link para esse produto.',
        });
        return;
      }

      const jobId = await requestGenerateLink(productUrl);
      const doneAffiliateUrl = await pollExtensionJob(jobId);
      currentAffiliateUrl = doneAffiliateUrl;
      await saveGeneratedLink(productUrl, { affiliate_url: doneAffiliateUrl, job_id: jobId });
      setBannerState('success', {
        title: 'Link de cashback pronto',
        text: 'Link de cashback pronto',
        subtext: 'Você já tem link para esse produto.',
      });
    } catch (err) {
      if (err?.code === 'login_required') {
        setBannerState('login-required', { text: 'Entre no MinhaOferta para gerar seu link com cashback.', subtext: '' });
      } else if (err?.message === 'timeout') {
        setBannerState('timeout', {
          text: 'Seu link ainda está sendo processado.',
          subtext: 'Acompanhe pelo MinhaOferta.',
        });
      } else {
        console.warn('[MinhaOferta] Falha ao gerar link pelo banner.');
        setBannerState('error', {
          text: 'Não foi possível gerar o link agora.',
          subtext: '',
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
    banner.innerHTML = '<button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button><strong class="mo-banner-title"></strong><p class="mo-banner-highlight"></p><p class="mo-banner-subtext"></p><div class="mo-banner-actions"></div>';
    banner.querySelector('.mo-banner-close')?.addEventListener('click', async () => { await rememberBannerClosed(window.location.href); banner.remove(); });
    setBannerState('initial', {
      text: 'Produto com cashback disponível.',
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
    } catch {
      console.warn('[MinhaOferta] Falha ao carregar preview do banner.');
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
    await cleanupExpiredGeneratedLinks();
    document.body.appendChild(createBanner());
    const stored = await getStoredGeneratedLinkForUrl(currentUrl);
    if (stored?.affiliate_url) {
      currentAffiliateUrl = stored.affiliate_url;
      setBannerState('success', {
        title: 'Link de cashback pronto',
        text: 'Link de cashback pronto',
        subtext: 'Você já tem link para esse produto.',
      });
      return;
    }
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
