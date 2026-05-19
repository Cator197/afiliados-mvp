const statusBoxElement = document.getElementById('popup-status-box');
const statusElement = document.getElementById('status-text');
const detailsElement = document.getElementById('status-details');
const noteElement = document.getElementById('status-note');
const urlElement = document.getElementById('current-url');
const generateButton = document.getElementById('simulate-btn');
const copyLinkButton = document.getElementById('copy-link-btn');
const openLinkButton = document.getElementById('open-link-btn');
const historyButton = document.getElementById('history-btn');
const checkButton = document.getElementById('check-page-btn');
const openSiteButton = document.getElementById('open-site-btn');
const BACKEND_BASE_URL = 'https://minhaoferta.com';
const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 20;
let currentPageState = { isMercadoLivre: false, isProductPage: false, url: '', loggedIn: false };
let generatedAffiliateLink = '';
let isGenerating = false;

const summarizeUrl = (u) => (!u ? '' : u.length <= 72 ? u : `${u.slice(0, 69)}...`);
const setStatusVariant = (v) => { statusBoxElement.classList.remove('status-neutral', 'status-success', 'status-loading', 'status-error'); statusBoxElement.classList.add(v); };

function setActions({ generate=false, copy=false, openLink=false, history=false }) {
  generateButton.hidden = !generate;
  copyLinkButton.hidden = !copy;
  openLinkButton.hidden = !openLink;
  historyButton.hidden = !history;
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...options });
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
  if (!preview.is_valid) {
    setStatusVariant('status-error');
    statusElement.textContent = 'Esta página não é compatível com o MinhaOferta.';
    detailsElement.textContent = 'Acesse uma página de produto do Mercado Livre para gerar seu link com cashback.';
    noteElement.textContent = '';
    setActions({});
  } else if (!preview.is_product_page) {
    setStatusVariant('status-neutral');
    statusElement.textContent = 'Você está no Mercado Livre, mas esta página não parece ser um produto.';
    detailsElement.textContent = 'Abra um produto específico para gerar o link com cashback.';
    noteElement.textContent = '';
    setActions({});
  } else if (!statusPayload?.logged_in) {
    setStatusVariant('status-neutral');
    statusElement.textContent = 'Entre no MinhaOferta para gerar seu link com cashback.';
    detailsElement.textContent = '';
    noteElement.textContent = 'Faça login para continuar.';
    setActions({});
  } else {
    setStatusVariant('status-success');
    statusElement.textContent = preview.estimated_cashback_label || 'Produto com cashback disponível.';
    detailsElement.textContent = preview.estimated_cashback_label ? 'Valor estimado. O cashback final depende da confirmação da compra.' : 'Gere seu link antes de comprar para participar do cashback.';
    noteElement.textContent = '';
    generateButton.disabled = false;
    generateButton.textContent = 'Gerar link com cashback';
    setActions({ generate: true });
  }
  urlElement.textContent = summarizeUrl(pageUrl || 'URL não disponível');
}

async function validateCurrentTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = activeTab?.url || '';
  try {
    const [statusResp, previewResp] = await Promise.all([
      fetchJson('/api/extension/status'),
      fetchJson('/api/extension/product-preview', { method: 'POST', body: JSON.stringify({ url }) })
    ]);
    renderState(previewResp.body, statusResp.body, url);
  } catch {
    setStatusVariant('status-error');
    statusElement.textContent = 'Não foi possível conectar ao MinhaOferta agora.';
    detailsElement.textContent = 'Verifique sua conexão e tente novamente.';
    noteElement.textContent = '';
    setActions({});
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
    generatedAffiliateLink = done.affiliate_url;
    setStatusVariant('status-success');
    statusElement.textContent = 'Link gerado com sucesso.';
    detailsElement.textContent = summarizeUrl(generatedAffiliateLink);
    noteElement.textContent = '';
    setActions({ copy: true, openLink: true, history: true });
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

checkButton.addEventListener('click', validateCurrentTab);
generateButton.addEventListener('click', startGenerateFlow);
copyLinkButton.addEventListener('click', async () => { if (generatedAffiliateLink) await navigator.clipboard.writeText(generatedAffiliateLink); });
openLinkButton.addEventListener('click', () => { if (generatedAffiliateLink) chrome.tabs.create({ url: generatedAffiliateLink }); });
historyButton.addEventListener('click', () => chrome.tabs.create({ url: `${BACKEND_BASE_URL}/historico` }));
openSiteButton.addEventListener('click', () => chrome.tabs.create({ url: BACKEND_BASE_URL }));
validateCurrentTab();
