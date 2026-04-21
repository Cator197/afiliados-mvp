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

function mensagemAmigavelErro(erro) {
    const texto = (erro || "").toLowerCase();

    if (texto.includes("sessão inválida") || texto.includes("expirada")) {
        return "Sua sessão expirou. Faça login novamente para continuar.";
    }
    if (texto.includes("url não informada")) {
        return "Informe a URL do produto para continuar.";
    }
    if (texto.includes("não pertence a uma plataforma suportada")) {
        return "URL inválida ou plataforma não suportada. Use links do Mercado Livre ou Shopee.";
    }
    if (texto.includes("não autorizado")) {
        return "Seu acesso expirou. Faça login novamente para continuar.";
    }
    if (texto.includes("não encontrado")) {
        return "Não encontramos seus dados agora. Atualize a página e tente novamente.";
    }

    return erro || "Não foi possível concluir sua solicitação agora. Tente novamente.";
}

function mostrarResultado(link) {
    resultBox.style.display = "block";
    resultBox.innerHTML = `
        <strong>Seu link afiliado foi gerado:</strong><br><br>
        <a href="${link}" target="_blank">${link}</a>
    `;
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

        if (status === "na_fila") {
            mostrarStatus("Sua solicitação foi recebida e está na fila de processamento.");
            return;
        }

        if (status === "processando") {
            mostrarStatus("Seu link está sendo gerado. Isso pode levar alguns instantes.");
            return;
        }

        if (status === "concluido") {
            const plataforma = labelPlataforma(job.plataforma);
            mostrarStatus(
                plataforma
                    ? `Link da ${plataforma} gerado com sucesso.`
                    : "Link gerado com sucesso."
            );
            mostrarResultado(job.resultado_link);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        if (status === "erro") {
            mostrarStatus(mensagemAmigavelErro(job.mensagem_erro), true);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        mostrarStatus(`Status atual: ${status}`);
    } catch (e) {
        mostrarStatus("Erro de comunicação ao consultar o status do job.", true);
        pararPolling();
        btnGerar.disabled = false;
    }
}

async function solicitarGeracao() {
    const url = inputUrl.value.trim();

    resultBox.style.display = "none";
    resultBox.innerHTML = "";

    if (!url) {
        mostrarStatus("Cole uma URL de produto do Mercado Livre ou Shopee antes de continuar.", true);
        return;
    }

    btnGerar.disabled = true;
    mostrarStatus("Enviando solicitação para a fila...");

    try {
        const resp = await fetch("/api/solicitar-link", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                codigo_usuario: window.USUARIO.codigo_usuario,
                url: url
            })
        });

        const data = await resp.json();

        if (!data.ok) {
            mostrarStatus(mensagemAmigavelErro(data.erro), true);
            btnGerar.disabled = false;
            return;
        }

        const jobId = data.job_id;
        const plataforma = labelPlataforma(data.plataforma);
        mostrarStatus(
            plataforma
                ? `Solicitação enviada para ${plataforma}. Aguardando processamento...`
                : "Solicitação enviada. Aguardando processamento..."
        );

        pararPolling();
        pollingInterval = setInterval(() => consultarJob(jobId), 2000);
        consultarJob(jobId);

    } catch (e) {
        mostrarStatus("Erro de comunicação com o servidor.", true);
        btnGerar.disabled = false;
    }
}

btnGerar.addEventListener("click", solicitarGeracao);

inputUrl.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        solicitarGeracao();
    }
});
