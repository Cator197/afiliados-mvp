import logging
import os
import time
from datetime import datetime

import requests

from bot_manager import get_bot, get_bot_status, set_bot_status
from config import (
    BOT_STATUS_AGUARDANDO_LOGIN,
    BOT_STATUS_ONLINE,
    VPS_BASE_URL,
    WORKER_API_TOKEN,
    WORKER_HEARTBEAT_INTERVAL_SECONDS,
    WORKER_ID,
    WORKER_POLL_INTERVAL_SECONDS,
)
from services.afiliado_bot import LoginNecessarioError


logger = logging.getLogger("remote_worker")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _build_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Worker-Token": WORKER_API_TOKEN,
        "X-Worker-Id": WORKER_ID,
    }


def _build_url(path: str) -> str:
    return f"{VPS_BASE_URL}{path}"


def _validate_local_config() -> None:
    if not VPS_BASE_URL:
        raise RuntimeError("VPS_BASE_URL não configurado.")
    if not WORKER_API_TOKEN:
        raise RuntimeError("WORKER_API_TOKEN não configurado.")
    if not WORKER_ID:
        raise RuntimeError("WORKER_ID não configurado.")


def claim_job() -> dict | None:
    response = requests.post(
        _build_url("/api/worker/jobs/claim"),
        headers=_build_headers(),
        json={"worker_id": WORKER_ID},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("erro") or "Falha ao claimar job")
    return payload.get("job")


def send_heartbeat(status: str, message: str | None = None) -> None:
    payload = {
        "worker_id": WORKER_ID,
        "status": status,
        "message": (message or "")[:500],
    }
    response = requests.post(
        _build_url("/api/worker/heartbeat"),
        headers=_build_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def maybe_send_heartbeat(last_sent_at: float, status: str, message: str | None = None) -> float:
    now_ts = time.monotonic()

    if now_ts - last_sent_at < WORKER_HEARTBEAT_INTERVAL_SECONDS:
        return last_sent_at

    try:
        send_heartbeat(status=status, message=message)
        logger.info("[WORKER] Heartbeat enviado | status=%s | message=%s", status, message or "-")
        return now_ts
    except requests.RequestException:
        logger.exception("[WORKER] Falha ao enviar heartbeat.")
        return last_sent_at


def send_success(job_id: str, url_afiliado: str) -> None:
    response = requests.post(
        _build_url(f"/api/worker/jobs/{job_id}/success"),
        headers=_build_headers(),
        json={"url_afiliado": url_afiliado},
        timeout=20,
    )
    response.raise_for_status()


def send_error(job_id: str, mensagem_erro: str) -> None:
    response = requests.post(
        _build_url(f"/api/worker/jobs/{job_id}/error"),
        headers=_build_headers(),
        json={"mensagem_erro": mensagem_erro[:500]},
        timeout=20,
    )
    response.raise_for_status()


def wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at: float):
    logger.warning(
        "[WORKER] Aguardando login manual no MESMO navegador do Selenium. "
        "O worker ficará pausado até a sessão ser restabelecida."
    )

    while True:
        last_heartbeat_sent_at = maybe_send_heartbeat(
            last_heartbeat_sent_at,
            status="aguardando_login_manual",
            message="Aguardando login manual no navegador persistente.",
        )

        try:
            if bot.esta_logado(passive_check=True) and bot.portal_pronto(passive_check=True):
                logger.info("[WORKER] Login manual detectado/restabelecido. Retomando processamento.")
                set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.")
                return bot, last_heartbeat_sent_at
        except Exception:
            logger.exception("[WORKER] Falha ao revalidar sessão durante espera de login manual.")

        time.sleep(WORKER_POLL_INTERVAL_SECONDS)


def ensure_bot_ready(bot, last_heartbeat_sent_at: float):
    status = get_bot_status()

    if status.get("status") == BOT_STATUS_AGUARDANDO_LOGIN:
        if bot.esta_logado(passive_check=True) and bot.portal_pronto(passive_check=True):
            set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.")
            return bot, last_heartbeat_sent_at
        return wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at)

    if not bot.esta_logado(force_check=True) or not bot.portal_pronto(force_check=True):
        return wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at)

    return bot, last_heartbeat_sent_at


def process_one_job(bot, job: dict) -> None:
    job_id = job["id"]
    url_original = (job.get("url_original") or "").strip()

    if not url_original:
        raise RuntimeError("url_original ausente no job claimado")

    logger.info("[JOB %s] Processando job com navegador persistente.", job_id)

    try:
        url_afiliado = bot.gerar_link(url_original)
        send_success(job_id=job_id, url_afiliado=url_afiliado)
        logger.info("[JOB %s] Job concluído com sucesso.", job_id)
    except LoginNecessarioError:
        logger.warning("[JOB %s] Login necessário detectado durante execução.", job_id)
        raise
    except Exception as exc:
        logger.exception("[JOB %s] Job concluído com erro.", job_id)
        send_error(job_id=job_id, mensagem_erro=str(exc))


def run() -> None:
    _validate_local_config()

    logger.info("[WORKER] Worker local iniciado. worker_id=%s vps=%s", WORKER_ID, VPS_BASE_URL)
    bot = get_bot()
    last_heartbeat_sent_at = 0.0

    bot, last_heartbeat_sent_at = ensure_bot_ready(bot, last_heartbeat_sent_at)
    logger.info("[WORKER] Navegador iniciado/reutilizado e pronto para polling.")

    while True:
        try:
            bot, last_heartbeat_sent_at = ensure_bot_ready(bot, last_heartbeat_sent_at)
            last_heartbeat_sent_at = maybe_send_heartbeat(
                last_heartbeat_sent_at,
                status="online",
                message="Worker em loop de polling.",
            )

            job = claim_job()

            if not job:
                time.sleep(WORKER_POLL_INTERVAL_SECONDS)
                continue

            logger.info("[JOB %s] Job claimado pelo worker=%s", job["id"], WORKER_ID)
            process_one_job(bot, job)
        except LoginNecessarioError:
            bot, last_heartbeat_sent_at = wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at)
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)
        except requests.RequestException:
            logger.exception("[WORKER] Falha de comunicação com a VPS. Tentando novamente.")
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)
        except Exception:
            logger.exception("[WORKER] Erro inesperado no loop principal.")
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    run()
