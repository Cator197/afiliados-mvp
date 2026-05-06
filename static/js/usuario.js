const btnGerar = document.getElementById("btnGerar");
const inputUrl = document.getElementById("urlProduto");
const statusBox = document.getElementById("statusBox");
const resultBox = document.getElementById("resultBox");

let pollingInterval = null;

function mostrarStatus(texto, tipo = "info") {
    statusBox.className = `status-box alert alert-${tipo}`;
    statusBox.textContent = texto;
    statusBox.setAttribute("role", tipo === "error" ? "alert" : "status");
    statusBox.setAttribute("aria-live", tipo === "error" ? "assertive" : "polite");
    statusBox.setAttribute("aria-busy", tipo === "loading" ? "true" : "false");
}

function setLoadingBotao(loading) {
    btnGerar.disabled = loading;
    btnGerar.setAttribute("aria-busy", loading ? "true" : "false");
    btnGerar.textContent = loading ? "Gerando link..." : "Gerar link com cashback";
}

function labelPlataforma(plataforma) {
    if (plataforma === "mercadolivre") return "Mercado Livre";
    if (plataforma === "shopee") return "Shopee (legado)";
    return "";
}

function statusHumano(status, plataforma = "") {
    if (status === "na_fila") {
        return "Recebemos sua solicitação e ela já entrou na fila. Próximo passo: aguarde o início do processamento.";
    }
    if (status === "processando") {
        return "Estamos gerando seu link com cashback. Próximo passo: aguarde a confirmação do link final.";
    }
    if (status === "concluido") {
        return plataforma
            ? `Tudo certo! Seu link da ${plataforma} foi gerado. Próximo passo: copie ou abra o link.`
            : "Tudo certo! Seu link foi gerado. Próximo passo: copie ou abra o link.";
    }
    if (status === "erro") {
        return "Não conseguimos gerar seu link desta vez. Próximo passo: revise a URL e tente novamente.";
    }
    return `A solicitação está em andamento (status: ${status}). Próximo passo: aguarde nova atualização.`;
}

function mensagemAmigavelErro(erro) {
    const texto = (erro || "").toLowerCase();

    if (texto.includes("sessão inválida") || texto.includes("expirada")) {
        return "Sua sessão expirou. Próximo passo: faça login novamente para continuar.";
    }
    if (texto.includes("url não informada")) {
        return "Não recebemos a URL do produto. Próximo passo: cole o link e tente novamente.";
    }
    if (texto.includes("não pertence a uma plataforma suportada")) {
        return "No momento aceitamos apenas links do Mercado Livre.";
    }
    if (texto.includes("não autorizado")) {
        return "Seu acesso não está autorizado agora. Próximo passo: faça login novamente.";
    }
    if (texto.includes("não encontrado")) {
        return "Não encontramos seus dados agora. Próximo passo: atualize a página e tente de novo.";
    }

    return erro || "Não foi possível concluir sua solicitação agora. Próximo passo: tente novamente em instantes.";
}

async function copiarLink(link) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(link);
            mostrarStatus("Link copiado com sucesso. Próximo passo: cole no navegador para finalizar sua compra.", "success");
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

        mostrarStatus("Link copiado com sucesso. Próximo passo: cole no navegador para finalizar sua compra.", "success");
    } catch (e) {
        mostrarStatus("Não foi possível copiar automaticamente. Próximo passo: copie manualmente o link abaixo.", "warning");
    }
}

function mostrarResultado(link) {
    const historicoUrl = `/historico/${encodeURIComponent(window.USUARIO.codigo_usuario)}`;

    resultBox.className = "result-box";
    resultBox.innerHTML = `
        <strong>✅ Seu link afiliado foi gerado.</strong>
        <p class="result-help">Próximo passo: copie ou abra o link para finalizar sua compra.</p>
        <a href="${link}" target="_blank" rel="noopener noreferrer" class="result-link" title="${link}">${link}</a>
        <div class="actions result-actions">
            <button id="btnCopiarLink" type="button">Copiar link</button>
            <a class="btn" href="${link}" target="_blank" rel="noopener noreferrer">Abrir link no site</a>
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
            mostrarStatus(mensagemAmigavelErro(data.erro), "error");
            pararPolling();
            setLoadingBotao(false);
            return;
        }

        const job = data.job;
        const status = job.status;

        if (status === "na_fila" || status === "processando") {
            mostrarStatus(statusHumano(status), "loading");
            return;
        }

        if (status === "concluido") {
            const plataforma = labelPlataforma(job.plataforma);
            mostrarStatus(statusHumano(status, plataforma), "success");
            mostrarResultado(job.resultado_link);
            pararPolling();
            setLoadingBotao(false);
            return;
        }

        if (status === "erro") {
            const erroDetalhado = mensagemAmigavelErro(job.mensagem_erro);
            mostrarStatus(`${statusHumano(status)} Detalhes: ${erroDetalhado}`, "error");
            pararPolling();
            setLoadingBotao(false);
            return;
        }

        mostrarStatus(statusHumano(status), "info");
    } catch (e) {
        mostrarStatus("Não foi possível consultar o andamento da solicitação. Próximo passo: tente novamente em instantes.", "error");
        pararPolling();
        setLoadingBotao(false);
    }
}

async function solicitarGeracao() {
    const url = inputUrl.value.trim();

    resultBox.className = "result-box is-hidden";
    resultBox.innerHTML = "";

    if (!url) {
        mostrarStatus("Link não informado. Próximo passo: cole uma URL do Mercado Livre ou Shopee para continuar.", "warning");
        return;
    }

    setLoadingBotao(true);
    mostrarStatus("Solicitando geração do link...", "loading");

    try {
        const resp = await fetch("/api/solicitar-link", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": window.USUARIO.csrf_token
            },
            body: JSON.stringify({
                url
            })
        });

        const data = await resp.json();

        if (!data.ok) {
            mostrarStatus(mensagemAmigavelErro(data.erro || "Erro ao gerar link."), "error");
            setLoadingBotao(false);
            return;
        }

        const plataforma = labelPlataforma(data.plataforma);
        mostrarStatus(
            plataforma
                ? `Solicitação recebida para ${plataforma}. Próximo passo: aguarde a geração do link.`
                : "Solicitação recebida. Próximo passo: aguarde a geração do link.",
            "info"
        );

        const jobId = data.job_id;
        pararPolling();
        pollingInterval = setInterval(() => consultarJob(jobId), 2000);
        consultarJob(jobId);
    } catch (e) {
        mostrarStatus("Não foi possível enviar sua solicitação ao servidor. Próximo passo: tente novamente em instantes.", "error");
        setLoadingBotao(false);
    }
}

btnGerar.addEventListener("click", solicitarGeracao);

inputUrl.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
        solicitarGeracao();
    }
});
