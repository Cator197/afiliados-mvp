const statusBoxElement = document.getElementById('popup-status-box');
const statusElement = document.getElementById('status-text');
const detailsElement = document.getElementById('status-details');
const noteElement = document.getElementById('status-note');
const urlElement = document.getElementById('current-url');
const generateButton = document.getElementById('simulate-btn');
const copyLinkButton = document.getElementById('copy-link-btn');
const openLinkButton = document.getElementById('open-link-btn');
const historyButton = document.getElementById('history-btn');
const openSiteButton = document.getElementById('open-site-btn');
const BACKEND_BASE_URL = 'https://minhaoferta.com';
const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 20;
const GENERATED_LINKS_STORAGE_KEY = 'generatedLinks';
const GENERATED_LINK_TTL_MS = 7 * 24 * 60 * 60 * 1000;
let currentPageState = { isMercadoLivre: false, isProductPage: false, url: '', loggedIn: false };
let historyUrl = `${BACKEND_BASE_URL}/historico`;
let generatedAffiliateLink = '';
let isGenerating = false;

const summarizeUrl = (u) => (!u ? '' : u.length <= 72 ? u : `${u.slice(0, 69)}...`);
const setStatusVariant = (v) => { statusBoxElement.classList.remove('status-neutral', 'status-success', 'status-loading', 'status-error'); statusBoxElement.classList.add(v); };


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
  return { normalizedUrl, entry };
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

function setActions({ generate=false, copy=false, openLink=false, history=false, login=false }) {
  generateButton.hidden = !generate;
  copyLinkButton.hidden = !copy;
  openLinkButton.hidden = !openLink;
  historyButton.hidden = !history;
  openSiteButton.hidden = !login;
}

function renderReadyLinkState(linkData) {
  generatedAffiliateLink = linkData.affiliate_url;
  setStatusVariant('status-success');
  statusElement.textContent = 'Link com cashback pronto.';
  detailsElement.textContent = linkData.estimated_cashback_label || 'Use este link para concluir sua compra com cashback.';
  noteElement.textContent = '';
  setActions({ openLink: true });
}

async function fetchJson(path, options = {}) {
  const targetUrl = path.startsWith('http') ? path : `${BACKEND_BASE_URL}${path}`;
  const response = await fetch(targetUrl, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...options });
  return { status: response.status, body: await response.json() };
}

async function pollJob(jobId) {
  for (let i=0;i<POLL_MAX_ATTEMPTS;i+=1) {
    const { status, body } = await fetchJson(`/api/extension/jobs/${jobId}`);
    if (status === 401) throw new Error('login_required');
    if (status === 404) throw new Error('job_not_found');
    if (body.status === 'success' && body.affiliate_url) return body;
    if (body.status === 'error') throw new Error('job_error');
    await new Promise((r)=>setTimeout(r,POLL_INTERVAL_MS));
  }
  throw new Error('timeout');
}

function renderState(preview, statusPayload, pageUrl) {
  currentPageState = { isMercadoLivre: preview.platform === 'mercadolivre', isProductPage: !!preview.is_product_page, url: pageUrl, loggedIn: !!statusPayload?.logged_in };
  historyUrl = statusPayload?.historico_url || `${BACKEND_BASE_URL}/historico`;
  if (!preview.is_valid) {
    setStatusVariant('status-error');
    statusElement.textContent = 'Esta página não é compatível com o MinhaOferta.';
    detailsElement.textContent = 'Acesse uma página de produto do Mercado Livre para gerar seu link com cashback.';
    noteElement.textContent = '';
    setActions({ login: !statusPayload?.logged_in });
  } else if (!preview.is_product_page) {
    setStatusVariant('status-neutral');
    statusElement.textContent = 'Você está no Mercado Livre, mas esta página não parece ser um produto.';
    detailsElement.textContent = 'Abra um produto específico para gerar o link com cashback.';
    noteElement.textContent = '';
    setActions({ login: !statusPayload?.logged_in });
  } else if (!statusPayload?.logged_in) {
    setStatusVariant('status-neutral');
    statusElement.textContent = 'Entre no MinhaOferta para gerar seu link com cashback.';
    detailsElement.textContent = '';
    noteElement.textContent = 'Faça login para continuar.';
    setActions({ login: true });
  } else {
    setStatusVariant('status-success');
    statusElement.textContent = preview.estimated_cashback_label || 'Produto com cashback disponível.';
    detailsElement.textContent = preview.estimated_cashback_label ? 'Valor estimado. O cashback final depende da confirmação da compra.' : 'Gere seu link antes de comprar para participar do cashback.';
    noteElement.textContent = '';
    generateButton.disabled = false;
    generateButton.textContent = 'Gerar link com cashback';
    setActions({ generate: true, login: false });
  }
  urlElement.textContent = summarizeUrl(pageUrl || 'URL não disponível');
}

async function validateCurrentTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = activeTab?.url || '';
  await cleanupExpiredGeneratedLinks();
  const stored = await getStoredGeneratedLinkForUrl(url);
  if (stored?.entry?.affiliate_url) {
    urlElement.textContent = summarizeUrl(url || 'URL não disponível');
    renderReadyLinkState(stored.entry);
    return;
  }
  try {
    const [statusResp, previewResp] = await Promise.all([
      fetchJson('https://minhaoferta.com/api/extension/status'),
      fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify({ url }) })
    ]);
    renderState(previewResp.body, statusResp.body, url);
  } catch {
    setStatusVariant('status-error');
    statusElement.textContent = 'Não foi possível conectar ao MinhaOferta agora.';
    detailsElement.textContent = 'Verifique sua conexão e tente novamente.';
    noteElement.textContent = '';
    setActions({ login: true });
  }
}

async function startGenerateFlow() {
  if (isGenerating || !currentPageState.isMercadoLivre || !currentPageState.isProductPage || !currentPageState.loggedIn) return;
  isGenerating = true;
  generateButton.disabled = true;
  generateButton.textContent = 'Gerando...';
  setStatusVariant('status-loading');
  statusElement.textContent = 'Gerando seu link com cashback...';
  detailsElement.textContent = 'Isso pode levar alguns segundos.';
  noteElement.textContent = '';
  setActions({ generate: true });
  try {
    const { status, body } = await fetchJson('/api/extension/generate-link', { method: 'POST', body: JSON.stringify({ url: currentPageState.url }) });
    if (status === 401 || body.error === 'login_required') throw new Error('login_required');
    if (body.error === 'invalid_url') throw new Error('invalid_url');
    if (body.error === 'not_product_page') throw new Error('not_product_page');
    const done = await pollJob(body.job_id);
    await saveGeneratedLink(currentPageState.url, { ...done, job_id: body.job_id });
    renderReadyLinkState({ ...done, estimated_cashback_label: done.estimated_cashback_label });
  } catch (err) {
    const code = err?.message;
    setStatusVariant('status-error');
    setActions({ generate: true, history: code === 'timeout' });
    if (code === 'login_required') {
      statusElement.textContent = 'Entre no MinhaOferta para gerar seu link com cashback.';
      detailsElement.textContent = 'Faça login e tente novamente.';
    } else if (code === 'invalid_url') {
      statusElement.textContent = 'Esta página não é compatível com o MinhaOferta.';
      detailsElement.textContent = 'Acesse uma página de produto do Mercado Livre para gerar seu link com cashback.';
    } else if (code === 'not_product_page') {
      statusElement.textContent = 'Você está no Mercado Livre, mas esta página não parece ser um produto.';
      detailsElement.textContent = 'Abra um produto específico para gerar o link com cashback.';
    } else if (code === 'timeout') {
      statusElement.textContent = 'Seu link ainda está sendo processado.';
      detailsElement.textContent = 'Você pode acompanhar pelo histórico.';
    } else {
      statusElement.textContent = 'Não foi possível conectar ao MinhaOferta agora.';
      detailsElement.textContent = 'Verifique sua conexão e tente novamente.';
    }
  } finally {
    isGenerating = false;
    generateButton.disabled = false;
    generateButton.textContent = 'Gerar link com cashback';
  }
}

generateButton.addEventListener('click', startGenerateFlow);
copyLinkButton.addEventListener('click', async () => { if (generatedAffiliateLink) await navigator.clipboard.writeText(generatedAffiliateLink); });
openLinkButton.addEventListener('click', () => { if (generatedAffiliateLink) chrome.tabs.create({ url: generatedAffiliateLink }); });
historyButton.addEventListener('click', () => chrome.tabs.create({ url: historyUrl }));
openSiteButton.addEventListener('click', () => chrome.tabs.create({ url: BACKEND_BASE_URL }));
validateCurrentTab();
