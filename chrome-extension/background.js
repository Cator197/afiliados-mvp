chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'MINHAOFERTA_PING') {
    sendResponse({ ok: true, status: 'ready' });
    return;
  }

  sendResponse({ ok: false, status: 'unknown_message' });
});
