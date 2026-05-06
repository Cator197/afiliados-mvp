import logging
import os
import time
from datetime import datetime

import requests

from bot_manager import get_bot, get_bot_status, get_existing_bot_or_none, get_existing_driver_status, set_bot_status
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
from services.platform_utils import ACTIVE_PLATFORMS, PLATFORM_MERCADOLIVRE, PLATFORM_SHOPEE


logger = logging.getLogger("remote_worker")
WORKER_REQUEST_TIMEOUT_SECONDS = 20


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _build_headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Worker-Token": WORKER_API_TOKEN,
        "X-Worker-Id": WORKER_ID,
        "User-Agent": f"afiliados-mvp-worker/{WORKER_ID}",
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


def _extract_response_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        return (payload.get("erro") or payload.get("message") or "").strip()

    return (response.text or "").strip()[:300]


def _raise_for_worker_response(response: requests.Response, operation: str) -> dict | None:
    if response.ok:
        if response.headers.get("Content-Type", "").lower().startswith("application/json"):
            return response.json()
        return None

    error_message = _extract_response_error(response)
    status_code = response.status_code

    if status_code in {401, 403}:
        raise RuntimeError(
            f"Autenticação do worker rejeitada em {operation} (status {status_code}). "
            f"{error_message or 'Verifique WORKER_API_TOKEN e X-Worker-Id.'}"
        )

    if status_code >= 500:
        raise RuntimeError(
            f"Falha da VPS em {operation} (status {status_code}). "
            f"{error_message or 'Erro interno no servidor.'}"
        )

    raise RuntimeError(
        f"Falha na requisição do worker em {operation} (status {status_code}). "
        f"{error_message or 'Resposta inválida da API.'}"
    )


def claim_job() -> dict | None:
    response = requests.post(
        _build_url("/api/worker/jobs/claim"),
        headers=_build_headers(),
        json={"worker_id": WORKER_ID},
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    payload = _raise_for_worker_response(response, "claim_job") or {}
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
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_worker_response(response, "heartbeat")


def maybe_send_heartbeat(last_sent_at: float, status: str, message: str | None = None) -> float:
    now_ts = time.monotonic()

    if now_ts - last_sent_at < WORKER_HEARTBEAT_INTERVAL_SECONDS:
        return last_sent_at

    try:
        send_heartbeat(status=status, message=message)
        logger.info("[WORKER] Heartbeat enviado | status=%s | message=%s", status, message or "-")
        return now_ts
    except (requests.RequestException, RuntimeError):
        logger.exception("[WORKER] Falha ao enviar heartbeat.")
        return last_sent_at


def send_success(job_id: str, url_afiliado: str) -> None:
    response = requests.post(
        _build_url(f"/api/worker/jobs/{job_id}/success"),
        headers=_build_headers(),
        json={"url_afiliado": url_afiliado},
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_worker_response(response, f"success job={job_id}")


def send_error(job_id: str, mensagem_erro: str) -> None:
    response = requests.post(
        _build_url(f"/api/worker/jobs/{job_id}/error"),
        headers=_build_headers(),
        json={"mensagem_erro": mensagem_erro[:500]},
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_worker_response(response, f"error job={job_id}")


def claim_healthcheck() -> dict | None:
    response = requests.post(
        _build_url("/api/worker/healthcheck/claim"),
        headers=_build_headers(),
        json={"worker_id": WORKER_ID},
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    payload = _raise_for_worker_response(response, "claim_healthcheck") or {}
    return payload.get("diagnostic")


def report_healthcheck_result(diagnostic_id: int, success: bool, payload: dict) -> None:
    endpoint = "success" if success else "error"
    response = requests.post(
        _build_url(f"/api/worker/healthcheck/{diagnostic_id}/{endpoint}"),
        headers=_build_headers(),
        json=payload,
        timeout=WORKER_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_for_worker_response(response, f"healthcheck_{endpoint} id={diagnostic_id}")


def wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at: float, plataforma: str):
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
                set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.", plataforma=plataforma)
                return bot, last_heartbeat_sent_at
        except Exception:
            logger.exception("[WORKER] Falha ao revalidar sessão durante espera de login manual.")

        time.sleep(WORKER_POLL_INTERVAL_SECONDS)


def ensure_bot_ready(bot, last_heartbeat_sent_at: float, plataforma: str):
    status = get_bot_status(plataforma=plataforma)

    if status.get("status") == BOT_STATUS_AGUARDANDO_LOGIN:
        if bot.esta_logado(passive_check=True) and bot.portal_pronto(passive_check=True):
            set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.", plataforma=plataforma)
            return bot, last_heartbeat_sent_at
        return wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at, plataforma=plataforma)

    if not bot.esta_logado(force_check=True) or not bot.portal_pronto(force_check=True):
        return wait_for_manual_login_if_needed(bot, last_heartbeat_sent_at, plataforma=plataforma)

    return bot, last_heartbeat_sent_at


def process_one_job(bot, job: dict) -> None:
    job_id = job["id"]
    url_original = (job.get("url_original") or "").strip()
    plataforma = (job.get("plataforma") or "mercadolivre").strip().lower()

    if not url_original:
        raise RuntimeError("url_original ausente no job claimado")
    if plataforma not in ACTIVE_PLATFORMS:
        mensagem = "Plataforma Shopee está desativada neste momento." if plataforma == PLATFORM_SHOPEE else f"Plataforma '{plataforma}' não suportada pelo worker."
        logger.warning("[JOB %s] %s", job_id, mensagem)
        send_error(job_id=job_id, mensagem_erro=mensagem)
        return

    logger.info("[MARKETPLACE DETECTADO] %s", plataforma)
    logger.info(
        "[WORKER] job %s enviado para bot %s.",
        job_id,
        "Mercado Livre",
    )
    logger.info("[JOB %s] Processando job da plataforma %s com navegador persistente.", job_id, plataforma)

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
    last_heartbeat_sent_at = 0.0
    logger.info("[WORKER] Polling iniciado.")
    plataforma_em_execucao = PLATFORM_MERCADOLIVRE

    while True:
        try:
            last_heartbeat_sent_at = maybe_send_heartbeat(
                last_heartbeat_sent_at,
                status="online",
                message="Worker em loop de polling.",
            )

            diagnostic = claim_healthcheck()
            if diagnostic:
                try:
                    logger.info("[HEALTHCHECK %s] iniciado pelo worker=%s", diagnostic["id"], WORKER_ID)
                    started_at = time.monotonic()
                    driver_status = get_existing_driver_status(plataforma=PLATFORM_MERCADOLIVRE)
                    bot = get_existing_bot_or_none(plataforma=PLATFORM_MERCADOLIVRE)

                    if bot is None:
                        result = {
                            "ok": False,
                            "etapa": "driver_ausente",
                            "mensagem": "Worker está vivo, mas não há navegador Selenium ativo para testar.",
                            "detalhes": f"worker_id={WORKER_ID} plataforma={PLATFORM_MERCADOLIVRE}",
                            "bot_status": "ausente",
                            "driver_status": "ausente" if not driver_status.get("driver_existe") else "quebrado",
                            "selenium_status": "nao_responsivo",
                            "ml_session": "indefinida",
                        }
                    else:
                        result = bot.healthcheck_passivo()
                        result["bot_status"] = "existente"
                        if not driver_status.get("driver_existe"):
                            result["driver_status"] = "ausente"
                        elif driver_status.get("driver_responsivo"):
                            result["driver_status"] = "existente"
                        else:
                            result["driver_status"] = "quebrado"

                    duration_ms = int((time.monotonic() - started_at) * 1000)
                    payload = {
                        "worker_vivo": True,
                        "plataforma": PLATFORM_MERCADOLIVRE,
                        "bot_status": result.get("bot_status", "existente" if bot else "ausente"),
                        "driver_status": result.get("driver_status", "existente"),
                        "selenium_status": result.get("selenium_status", "responsivo"),
                        "ml_session": result.get("ml_session", "indefinida"),
                        "etapa": result.get("etapa"),
                        "mensagem": result.get("mensagem"),
                        "detalhes": result.get("detalhes"),
                        "duracao_ms": duration_ms,
                    }
                    report_healthcheck_result(diagnostic["id"], bool(result.get("ok")), payload)
                    logger.info("[HEALTHCHECK %s] finalizado status=%s", diagnostic["id"], "ok" if result.get("ok") else "erro")
                except Exception as exc:
                    logger.exception("[HEALTHCHECK %s] erro inesperado durante execução passiva.", diagnostic["id"])
                    payload = {
                        "worker_vivo": True,
                        "plataforma": PLATFORM_MERCADOLIVRE,
                        "bot_status": "indefinido",
                        "driver_status": "quebrado",
                        "selenium_status": "nao_responsivo",
                        "ml_session": "indefinida",
                        "etapa": "healthcheck_exception",
                        "mensagem": "Erro inesperado no health check passivo do worker.",
                        "detalhes": str(exc)[:500],
                    }
                    report_healthcheck_result(diagnostic["id"], False, payload)
                time.sleep(1)
                continue

            job = claim_job()

            if not job:
                time.sleep(WORKER_POLL_INTERVAL_SECONDS)
                continue

            logger.info("[JOB %s] Job claimado pelo worker=%s", job["id"], WORKER_ID)
            plataforma = (job.get("plataforma") or PLATFORM_MERCADOLIVRE).strip().lower()
            plataforma_em_execucao = plataforma
            if plataforma not in ACTIVE_PLATFORMS:
                mensagem = "Plataforma Shopee está desativada neste momento." if plataforma == PLATFORM_SHOPEE else f"Plataforma '{plataforma}' não suportada."
                send_error(job_id=job["id"], mensagem_erro=mensagem)
                continue

            bot = get_bot(plataforma=plataforma, job_id=job["id"])
            bot, last_heartbeat_sent_at = ensure_bot_ready(
                bot,
                last_heartbeat_sent_at,
                plataforma=plataforma,
            )
            process_one_job(bot, job)
        except LoginNecessarioError:
            bot = get_bot(plataforma=plataforma_em_execucao)
            bot, last_heartbeat_sent_at = wait_for_manual_login_if_needed(
                bot,
                last_heartbeat_sent_at,
                plataforma=plataforma_em_execucao,
            )
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
