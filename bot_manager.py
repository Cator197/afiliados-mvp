import threading
import logging
import os
import getpass

from services.browser_manager import criar_driver, liberar_profile_em_uso
from services.afiliado_bot import AfiliadoBot
from config import (
    BOT_STATUS_OFFLINE,
    BOT_STATUS_RECRIANDO,
    BOT_STATUS_ONLINE,
    BOT_STATUS_AGUARDANDO_LOGIN,
    BOT_STATUS_ERRO_RECUPERACAO,
    CHROME_DISPLAY,
    CHROME_PROFILE_DIR,
)


_driver = None
_bot = None
_bot_lock = threading.Lock()
logger = logging.getLogger(__name__)

_bot_status = BOT_STATUS_OFFLINE
_bot_message = "Bot ainda não inicializado."


def set_bot_status(status, message):
    global _bot_status, _bot_message
    _bot_status = status
    _bot_message = message
    logger.info("[BOT STATUS] %s - %s", status, message)


def get_bot_status():
    return {
        "status": _bot_status,
        "message": _bot_message,
        "display": os.getenv("DISPLAY"),
        "chrome_profile_dir": str(CHROME_PROFILE_DIR.resolve()),
    }


def driver_esta_vivo(driver) -> bool:
    if driver is None:
        return False

    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def _job_tag(job_id: str | None) -> str:
    return f"[JOB {job_id}] " if job_id else ""


def _log_ambiente_selenium(job_id: str | None = None):
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = os.getenv("USER", "desconhecido")

    prefixo = _job_tag(job_id)
    logger.info(
        "%sContexto Selenium: DISPLAY=%s | CHROME_DISPLAY=%s | CHROME_PROFILE_DIR=%s | user=%s",
        prefixo,
        os.getenv("DISPLAY"),
        CHROME_DISPLAY,
        CHROME_PROFILE_DIR,
        usuario,
    )


def criar_nova_instancia(job_id: str | None = None):
    global _driver, _bot

    try:
        logger.info("%sCriando nova instância do bot.", _job_tag(job_id))
        _log_ambiente_selenium(job_id)
        set_bot_status(BOT_STATUS_RECRIANDO, "Recriando navegador do robô...")

        _driver = criar_driver()
        _bot = AfiliadoBot(_driver, atualizar_status=set_bot_status)
        logger.info("%sInstância do bot criada com sucesso.", _job_tag(job_id))

        set_bot_status(BOT_STATUS_AGUARDANDO_LOGIN, "Verificando sessão do Mercado Livre...")

        _bot.garantir_portal_pronto()
        if not _bot.esta_logado():
            set_bot_status(
                BOT_STATUS_AGUARDANDO_LOGIN,
                "Navegador oficial do robô está aberto no Selenium (via DISPLAY/VNC) aguardando login manual no perfil persistente."
            )
            logger.warning(
                "%sBot criado, porém requer login manual no mesmo Chrome do Selenium. DISPLAY=%s | profile=%s",
                _job_tag(job_id),
                os.getenv("DISPLAY"),
                CHROME_PROFILE_DIR.resolve(),
            )
            return _bot

        set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.")
        logger.info("%sBot pronto para uso.", _job_tag(job_id))
        return _bot

    except Exception as e:
        set_bot_status(
            BOT_STATUS_ERRO_RECUPERACAO,
            f"Não foi possível recuperar o robô automaticamente: {e}"
        )
        logger.exception("%sFalha ao criar/recriar instância do bot.", _job_tag(job_id))
        raise


def get_bot(job_id: str | None = None):
    global _bot, _driver

    with _bot_lock:
        driver_vivo = driver_esta_vivo(_driver)
        bot_com_driver_valido = _bot is not None and getattr(_bot, "driver", None) is _driver

        if not driver_vivo or not bot_com_driver_valido:
            logger.warning(
                "%sDriver indisponível/inválido (driver_vivo=%s, bot_com_driver_valido=%s). Recriando bot.",
                _job_tag(job_id),
                driver_vivo,
                bot_com_driver_valido,
            )
            if _driver is not None:
                try:
                    _driver.quit()
                except Exception:
                    logger.warning(
                        "%sFalha ao encerrar driver inválido; liberando lock de profile de forma defensiva.",
                        _job_tag(job_id),
                    )
                    liberar_profile_em_uso()
            _driver = None
            _bot = None
            return criar_nova_instancia(job_id=job_id)

        logger.info("%sReusando instância atual do bot e sessão ativa do navegador.", _job_tag(job_id))
        return _bot


def reiniciar_bot(job_id: str | None = None):
    global _driver, _bot

    with _bot_lock:
        logger.warning("%sReiniciando bot sob demanda.", _job_tag(job_id))
        try:
            if _driver is not None:
                _driver.quit()
                logger.info("%sDriver anterior encerrado com sucesso.", _job_tag(job_id))
        except Exception:
            logger.exception("%sFalha ao encerrar driver anterior durante reinício.", _job_tag(job_id))
            liberar_profile_em_uso()

        _driver = None
        _bot = None

        return criar_nova_instancia(job_id=job_id)
