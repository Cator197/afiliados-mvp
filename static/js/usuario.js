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
            mostrarStatus(data.erro || "Não foi possível consultar o job.", true);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        const job = data.job;
        const status = job.status;

        if (status === "na_fila") {
            mostrarStatus("Sua solicitação está na fila...");
            return;
        }

        if (status === "processando") {
            mostrarStatus("Seu link está sendo gerado...");
            return;
        }

        if (status === "concluido") {
            mostrarStatus("Link gerado com sucesso.");
            mostrarResultado(job.resultado_link);
            pararPolling();
            btnGerar.disabled = false;
            return;
        }

        if (status === "erro") {
            mostrarStatus(job.mensagem_erro || "Ocorreu um erro ao gerar o link.", true);
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
        mostrarStatus("Cole uma URL do Mercado Livre antes de continuar.", true);
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
            mostrarStatus(data.erro || "Não foi possível solicitar a geração.", true);
            btnGerar.disabled = false;
            return;
        }

        const jobId = data.job_id;
        mostrarStatus("Solicitação enviada. Aguardando processamento...");

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