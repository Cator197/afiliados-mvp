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

    function handleQuickStatusButtons(form) {
        const quickButtons = form.querySelectorAll('.btn-quick-status');
        const statusSelect = form.querySelector('select[name="status"]');

        quickButtons.forEach((button) => {
            button.addEventListener('click', function () {
                if (!statusSelect) {
                    return;
                }

                const targetStatus = button.dataset.quickStatus;
                const confirmMessage = button.dataset.confirmMessage || 'Confirmar ação?';

                if (!targetStatus) {
                    return;
                }

                if (!window.confirm(confirmMessage)) {
                    return;
                }

                statusSelect.value = targetStatus;
                form.requestSubmit();
            });
        });
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
            handleQuickStatusButtons(form);
            handleSubmitFeedback(form);
        });

        handleFilterLoading();
    };
})();
