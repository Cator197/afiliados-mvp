const btnGerar = document.getElementById("btnGerar");
const inputUrl = document.getElementById("urlProduto");
const statusBox = document.getElementById("statusBox");
const resultBox = document.getElementById("resultBox");

let pollingInterval = null;

function mostrarStatus(texto, erro = false) {
    statusBox.style.display = "block";
    statusBox.textContent = texto;
    statusBox.style.borderColor = erro ? "#f0b7b7" : "#e4e8ee";
    statusBox.style.background = erro ? "#fff3f3" : "#f7f8fa";
}

function labelPlataforma(plataforma) {
    if (plataforma === "mercadolivre") return "Mercado Livre";
    if (plataforma === "shopee") return "Shopee";
    return "";
}

function statusHumano(status, plataforma = "") {
    if (status === "na_fila") {
        return "Recebemos sua solicitação e ela já entrou na fila. Próximo passo: aguardar o início do processamento.";
    }
    if (status === "processando") {
        return "Estamos gerando seu link com cashback agora. Próximo passo: aguarde a confirmação do link final.";
    }
    if (status === "concluido") {
        return plataforma
            ? `Tudo certo! Seu link da ${plataforma} foi gerado. Próximo passo: copie ou abra o link para finalizar sua compra.`
            : "Tudo certo! Seu link foi gerado. Próximo passo: copie ou abra o link para finalizar sua compra.";
    }
    if (status === "erro") {
        return "Não conseguimos gerar seu link desta vez. Próximo passo: revise a URL enviada e tente novamente.";
    }
    return `A solicitação está em andamento (status: ${status}). Próximo passo: aguarde nova atualização.`;
}

function mensagemAmigavelErro(erro) {
    const texto = (erro || "").toLowerCase();

    if (texto.includes("sessão inválida") || texto.includes("expirada")) {
        return "Sua sessão expirou. O que aconteceu: seu login perdeu validade. Próximo passo: faça login novamente para continuar.";
    }
    if (texto.includes("url não informada")) {
        return "Não recebemos a URL do produto. Próximo passo: cole o link e tente novamente.";
    }
    if (texto.includes("não pertence a uma plataforma suportada")) {
        return "O link enviado não é válido para esta área. Próximo passo: use links do Mercado Livre ou Shopee e tente de novo.";
    }
    if (texto.includes("não autorizado")) {
        return "Seu acesso não está autorizado no momento. Próximo passo: faça login novamente e tente de novo.";
    }
    if (texto.includes("não encontrado")) {
        return "Não encontramos seus dados agora. Próximo passo: atualize a página e repita a solicitação.";
    }

    return erro || "Não foi possível concluir sua solicitação agora. Próximo passo: tente novamente em alguns instantes.";
}

async function copiarLink(link) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(link);
            mostrarStatus("Link copiado com sucesso. Próximo passo: cole no navegador para finalizar sua compra.");
            return;
        }

        const inputAux = document.createElement("textarea");
        inputAux.value = link;
        inputAux.setAttribute("readonly", "");
        inputAux.style.position = "absolute";
        inputAux.style.left = "-9999px";
        document.body.appendChild(inputAux);
        inputAux.select();
        document.execCommand("copy");
        document.body.removeChild(inputAux);

        mostrarStatus("Link copiado com sucesso. Próximo passo: cole no navegador para finalizar sua compra.");
    } catch (e) {
        mostrarStatus("Não foi possível copiar automaticamente. Próximo passo: copie manualmente o link exibido abaixo.", true);
    }
}

function mostrarResultado(link) {
    const historicoUrl = `/historico/${encodeURIComponent(window.USUARIO.codigo_usuario)}`;

    resultBox.style.display = "block";
    resultBox.innerHTML = `
        <strong>Seu link afiliado foi gerado.</strong>
        <p class="result-help">O que aconteceu: a geração foi concluída com sucesso. Próximo passo: copie ou abra o link para comprar.</p>
        <a href="${link}" target="_blank" rel="noopener noreferrer" class="result-link" title="${link}">${link}</a>
        <div class="actions result-actions">
            <button id="btnCopiarLink" type="button">Copiar link</button>
            <a class="btn" href="${link}" target="_blank" rel="noopener noreferrer">Abrir link</a>
            <a class="btn btn-secondary" href="${historicoUrl}">Ver histórico</a>
        </div>
    `;

    const btnCopiarLink = document.getElementById("btnCopiarLink");
    if (btnCopiarLink) {
        btnCopiarLink.addEventListener("click", () => copiarLink(link));
    }
}

function pararPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

async function consultarJob(jobId) {
    try {
        const resp = await fetch(`/api/jobs/${jobId}`);
        const data = await resp.json();

        if (!data.ok) {
            mostrarStatus(mensagemAmigavelErro(data.erro), true);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        const job = data.job;
        const status = job.status;

        if (status === "na_fila" || status === "processando") {
            mostrarStatus(statusHumano(status));
            return;
        }

        if (status === "concluido") {
            const plataforma = labelPlataforma(job.plataforma);
            mostrarStatus(statusHumano(status, plataforma));
            mostrarResultado(job.resultado_link);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        if (status === "erro") {
            const erroDetalhado = mensagemAmigavelErro(job.mensagem_erro);
            mostrarStatus(`${statusHumano(status)} Detalhes: ${erroDetalhado}`, true);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        mostrarStatus(statusHumano(status));
    } catch (e) {
        mostrarStatus("Não foi possível consultar o andamento da solicitação. Próximo passo: aguarde alguns segundos e tente novamente.", true);
        pararPolling();
        btnGerar.disabled = false;
    }
}

async function solicitarGeracao() {
    const url = inputUrl.value.trim();

    resultBox.style.display = "none";
    resultBox.innerHTML = "";

    if (!url) {
        mostrarStatus("Não recebemos o link do produto. Próximo passo: cole uma URL do Mercado Livre ou Shopee e continue.", true);
        return;
    }

    btnGerar.disabled = true;
    mostrarStatus("Solicitação enviada. Próximo passo: aguarde enquanto incluímos seu pedido na fila.");

    try {
        const resp = await fetch("/api/solicitar-link", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": window.USUARIO.csrf_token
            },
            body: JSON.stringify({
                url: url
            })
        });

        const data = await resp.json();

        if (!data.ok) {
            mostrarStatus(mensagemAmigavelErro(data.erro), true);
            btnGerar.disabled = false;
            return;
        }

        const plataforma = labelPlataforma(data.plataforma);
        mostrarStatus(
            plataforma
                ? `Solicitação recebida para ${plataforma}. Próximo passo: aguardar a geração do link.`
                : "Solicitação recebida. Próximo passo: aguardar a geração do link."
        );

        const jobId = data.job_id;
        pararPolling();
        pollingInterval = setInterval(() => consultarJob(jobId), 2000);
        consultarJob(jobId);
    } catch (e) {
        mostrarStatus("Não foi possível enviar sua solicitação ao servidor. Próximo passo: tente novamente em alguns instantes.", true);
        btnGerar.disabled = false;
    }
}

btnGerar.addEventListener("click", solicitarGeracao);

inputUrl.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        solicitarGeracao();
    }
});
