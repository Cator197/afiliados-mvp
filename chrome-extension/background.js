const isDevelopmentMode = !('update_url' in chrome.runtime.getManifest());

if (isDevelopmentMode) {
  console.debug('[MinhaOferta] Background service worker inicializado (modo desenvolvimento).');
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'MINHAOFERTA_PING') {
    sendResponse({ ok: true, status: 'ready' });
    return;
  }

  sendResponse({ ok: false, status: 'unknown_message' });
});
