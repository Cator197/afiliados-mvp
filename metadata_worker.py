import logging
import time
from datetime import datetime

import requests

from config import (
    VPS_BASE_URL,
    WORKER_API_TOKEN,
    WORKER_ID,
    WORKER_POLL_INTERVAL_SECONDS,
)
from services.product_metadata_bot import ProductMetadataBot
from services.product_metadata_browser import create_metadata_driver


logger = logging.getLogger("metadata_worker")
REQUEST_TIMEOUT_SECONDS = 30


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Worker-Token": WORKER_API_TOKEN,
        "X-Worker-Id": WORKER_ID,
        "User-Agent": f"afiliados-mvp-metadata-worker/{WORKER_ID}",
    }


def _url(path: str) -> str:
    return f"{VPS_BASE_URL}{path}"


def _validate_config():
    if not VPS_BASE_URL:
        raise RuntimeError("VPS_BASE_URL não configurado.")
    if not WORKER_API_TOKEN:
        raise RuntimeError("WORKER_API_TOKEN não configurado.")
    if not WORKER_ID:
        raise RuntimeError("WORKER_ID não configurado.")


def claim_metadata_job() -> dict | None:
    response = requests.post(
        _url("/api/worker/metadata/claim"),
        headers=_headers(),
        json={"worker_id": WORKER_ID},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("erro") or "Falha ao claimar metadata job")
    return payload.get("metadata_job")


def send_metadata_success(link_id: int, metadata: dict):
    response = requests.post(
        _url(f"/api/worker/metadata/{link_id}/success"),
        headers=_headers(),
        json=metadata,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def send_metadata_error(link_id: int, mensagem_erro: str):
    response = requests.post(
        _url(f"/api/worker/metadata/{link_id}/error"),
        headers=_headers(),
        json={"mensagem_erro": mensagem_erro[:500]},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def run():
    _validate_config()
    logger.info("[METADATA] Worker iniciado. worker_id=%s", WORKER_ID)

    try:
        driver = create_metadata_driver()
    except Exception as exc:
        logger.exception("[METADATA] Falha ao iniciar Chrome/driver: %s", exc)
        raise RuntimeError(
            "Não foi possível iniciar o Chrome do metadata_worker. "
            "Verifique CHROME_BINARY_PATH, METADATA_CHROME_PROFILE_DIR e lock de perfil."
        ) from exc

    bot = ProductMetadataBot(driver=driver)

    while True:
        link_id = None
        try:
            job = claim_metadata_job()
            if not job:
                time.sleep(WORKER_POLL_INTERVAL_SECONDS)
                continue

            link_id = int(job["id"])
            url_original = (job.get("url_original") or "").strip()
            percentual_cashback = job.get("percentual_cashback")
            logger.info("[METADATA %s] Job claimado para URL: %s", link_id, url_original)

            metadata = bot.extrair_metadados(url_original)
            metadata["percentual_cashback"] = percentual_cashback
            metadata["processado_em"] = now_str()

            send_metadata_success(link_id=link_id, metadata=metadata)
            logger.info("[METADATA %s] Metadados enviados com sucesso.", link_id)
        except Exception as exc:
            logger.exception("[METADATA] Falha no loop de processamento")
            if isinstance(link_id, int):
                try:
                    send_metadata_error(link_id=link_id, mensagem_erro=str(exc))
                except Exception:
                    logger.exception("[METADATA %s] Falha ao reportar erro para API", link_id)
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
