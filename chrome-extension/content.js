(function initMinhaOfertaBanner() {
  const host = window.location.hostname;
  const isMercadoLivre = host === 'www.mercadolivre.com.br' || host === 'mercadolivre.com.br';

  if (!isMercadoLivre) {
    return;
  }

  if (document.getElementById('mo-cashback-banner')) {
    return;
  }

  const banner = document.createElement('aside');
  banner.id = 'mo-cashback-banner';
  banner.className = 'mo-banner';
  banner.setAttribute('role', 'complementary');
  banner.setAttribute('aria-label', 'Banner MinhaOferta');

  banner.innerHTML = `
    <button type="button" class="mo-banner-close" aria-label="Fechar banner">×</button>
    <strong class="mo-banner-title">MinhaOferta</strong>
    <p class="mo-banner-text">Gere o link para receber cashback.</p>
    <button type="button" class="mo-banner-action">Em breve</button>
  `;

  document.body.appendChild(banner);

  const closeButton = banner.querySelector('.mo-banner-close');
  const actionButton = banner.querySelector('.mo-banner-action');

  closeButton?.addEventListener('click', () => {
    banner.remove();
  });

  actionButton?.addEventListener('click', () => {
    // Intencionalmente sem integração nesta fase inicial (PR 2).
  });
})();
