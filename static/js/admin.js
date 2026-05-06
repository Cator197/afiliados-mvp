(function () {
    function garantirAvisoGlobal() {
        let box = document.getElementById('adminFeedbackBox');
        if (!box) {
            box = document.createElement('div');
            box.id = 'adminFeedbackBox';
            box.className = 'message-box is-hidden';
            box.setAttribute('role', 'status');
            box.setAttribute('aria-live', 'polite');

            const container = document.querySelector('.container');
            if (container) {
                container.insertBefore(box, container.children[1] || null);
            }
        }
        return box;
    }

    function mostrarAvisoGlobal(texto, tipo) {
        const box = garantirAvisoGlobal();
        box.className = `message-box alert alert-${tipo}`;
        box.textContent = texto;
    }


    function handleSubmitFeedback(form) {
        form.addEventListener('submit', function (event) {
            const statusSelect = form.querySelector('select[name="status"]');
            const submitter = event.submitter || form.querySelector('button[type="submit"]');

            if (statusSelect && statusSelect.value === 'cashback_pago') {
                const ok = window.confirm('Tem certeza que deseja marcar este link como cashback pago?');
                if (!ok) {
                    event.preventDefault();
                    return;
                }
            }

            const buttons = form.querySelectorAll('button');
            buttons.forEach((btn) => {
                btn.disabled = true;
            });

            if (submitter) {
                submitter.dataset.defaultText = submitter.dataset.defaultText || submitter.textContent;
                submitter.textContent = 'Salvando atualização...';
            }

            mostrarAvisoGlobal('Salvando atualização do link. Aguarde a confirmação da página.', 'loading');
        });
    }

    function handleMetadataRefreshButton(form) {
        const actionsContainer = form.querySelector('[data-link-actions="true"]');
        const refreshButton = form.querySelector('.btn-refresh-metadata');
        const statusLabel = form.querySelector('.metadata-status-label');
        const errorText = form.querySelector('.metadata-error-text');

        if (!actionsContainer || !refreshButton) {
            return;
        }

        const endpoint = actionsContainer.dataset.metadataEndpoint;
        const csrfToken = actionsContainer.dataset.csrfToken;

        refreshButton.addEventListener('click', async function () {
            if (!endpoint || !csrfToken) {
                mostrarAvisoGlobal('Não foi possível enviar o link para a fila de metadados.', 'error');
                return;
            }

            refreshButton.disabled = true;
            const previousText = refreshButton.textContent;
            refreshButton.textContent = 'Enviando...';

            try {
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRF-Token': csrfToken,
                        'Accept': 'application/json',
                    },
                });
                const data = await resp.json();

                if (!resp.ok || !data.ok) {
                    throw new Error(data.erro || 'Falha ao enfileirar atualização.');
                }

                if (statusLabel) {
                    statusLabel.textContent = 'pendente';
                }
                if (errorText) {
                    errorText.textContent = '';
                }

                mostrarAvisoGlobal(data.mensagem || 'Atualização enviada para a fila.', 'success');
            } catch (error) {
                mostrarAvisoGlobal(error.message || 'Erro ao atualizar metadados.', 'error');
            } finally {
                refreshButton.disabled = false;
                refreshButton.textContent = previousText;
            }
        });
    }


    function handleSendTestEmail() {
        const button = document.getElementById('sendTestEmailBtn');
        const resultBox = document.getElementById('emailTestResult');

        if (!button || !resultBox) {
            return;
        }

        const csrfToken = button.dataset.csrfToken || '';

        button.addEventListener('click', async function () {
            button.disabled = true;
            const previousText = button.textContent;
            button.textContent = 'Enviando...';
            resultBox.textContent = 'Enviando e-mail de teste...';

            try {
                const resp = await fetch('/api/admin/email/test', {
                    method: 'POST',
                    headers: {
                        'X-CSRF-Token': csrfToken,
                        'Accept': 'application/json',
                    },
                });
                const data = await resp.json();
                resultBox.textContent = data.message || (data.ok ? 'E-mail enviado.' : 'Falha ao enviar e-mail.');
                mostrarAvisoGlobal(resultBox.textContent, data.ok ? 'success' : 'error');
            } catch (error) {
                resultBox.textContent = 'Erro ao enviar e-mail de teste.';
                mostrarAvisoGlobal(resultBox.textContent, 'error');
            } finally {
                button.disabled = false;
                button.textContent = previousText;
            }
        });
    }

    function handleFilterLoading() {
        const filterForm = document.querySelector('form[data-admin-filter="true"]');
        if (!filterForm) {
            return;
        }

        filterForm.addEventListener('submit', function () {
            mostrarAvisoGlobal('Aplicando filtros e atualizando a lista...', 'loading');
        });
    }

    window.initAdminLinksPage = function initAdminLinksPage() {
        const forms = document.querySelectorAll('table tbody form');
        forms.forEach((form) => {
            handleSubmitFeedback(form);
            handleMetadataRefreshButton(form);
        });

        handleFilterLoading();
        handleSendTestEmail();
    };
})();
