import threading
import logging
import os
import getpass

from services.browser_manager import criar_driver, liberar_profile_em_uso
from services.afiliado_bot import AfiliadoBot
from services.shopee_bot import ShopeeBot
from services.platform_utils import PLATFORM_MERCADOLIVRE, PLATFORM_SHOPEE
from config import (
    BOT_STATUS_OFFLINE,
    BOT_STATUS_RECRIANDO,
    BOT_STATUS_ONLINE,
    BOT_STATUS_AGUARDANDO_LOGIN,
    BOT_STATUS_ERRO_RECUPERACAO,
    CHROME_DISPLAY,
    CHROME_PROFILE_DIR,
)


_drivers = {}
_bots = {}
_bot_lock = threading.Lock()
logger = logging.getLogger(__name__)

_bot_status = {
    PLATFORM_MERCADOLIVRE: BOT_STATUS_OFFLINE,
    PLATFORM_SHOPEE: BOT_STATUS_OFFLINE,
}
_bot_message = {
    PLATFORM_MERCADOLIVRE: "Bot ainda não inicializado.",
    PLATFORM_SHOPEE: "Bot ainda não inicializado.",
}


def set_bot_status(status, message, plataforma: str = PLATFORM_MERCADOLIVRE):
    _bot_status[plataforma] = status
    _bot_message[plataforma] = message
    logger.info("[BOT STATUS] plataforma=%s | %s - %s", plataforma, status, message)


def get_bot_status(plataforma: str = PLATFORM_MERCADOLIVRE):
    return {
        "status": _bot_status.get(plataforma, BOT_STATUS_OFFLINE),
        "message": _bot_message.get(plataforma, "Bot ainda não inicializado."),
        "plataforma": plataforma,
        "display": os.getenv("DISPLAY"),
        "chrome_profile_dir": str((CHROME_PROFILE_DIR.resolve() / plataforma)),
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


def _build_bot(driver, plataforma: str):
    atualizar_status = lambda status, message: set_bot_status(status, message, plataforma=plataforma)
    if plataforma == PLATFORM_SHOPEE:
        return ShopeeBot(driver, atualizar_status=atualizar_status)
    return AfiliadoBot(driver, atualizar_status=atualizar_status)


def _plataforma_label(plataforma: str) -> str:
    return "Shopee" if plataforma == PLATFORM_SHOPEE else "Mercado Livre"


def criar_nova_instancia(job_id: str | None = None, plataforma: str = PLATFORM_MERCADOLIVRE):

    try:
        logger.info("%sCriando nova instância do bot da plataforma %s.", _job_tag(job_id), plataforma)
        _log_ambiente_selenium(job_id)
        set_bot_status(BOT_STATUS_RECRIANDO, "Recriando navegador do robô...", plataforma=plataforma)

        driver = criar_driver(plataforma=plataforma)
        bot = _build_bot(driver, plataforma=plataforma)
        _drivers[plataforma] = driver
        _bots[plataforma] = bot
        logger.info("%sInstância do bot criada com sucesso para %s.", _job_tag(job_id), plataforma)

        set_bot_status(
            BOT_STATUS_AGUARDANDO_LOGIN,
            f"Verificando sessão do {_plataforma_label(plataforma)}...",
            plataforma=plataforma,
        )

        bot.garantir_portal_pronto()
        if not bot.esta_logado():
            set_bot_status(
                BOT_STATUS_AGUARDANDO_LOGIN,
                f"Navegador oficial do robô {_plataforma_label(plataforma)} está aberto no Selenium aguardando login manual no perfil persistente.",
                plataforma=plataforma,
            )
            logger.warning(
                "%sBot %s criado, porém requer login manual no mesmo Chrome do Selenium. DISPLAY=%s | profile=%s",
                _job_tag(job_id),
                plataforma,
                os.getenv("DISPLAY"),
                (CHROME_PROFILE_DIR.resolve() / plataforma),
            )
            return bot

        set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.", plataforma=plataforma)
        logger.info("%sBot pronto para uso na plataforma %s.", _job_tag(job_id), plataforma)
        return bot

    except Exception as e:
        set_bot_status(
            BOT_STATUS_ERRO_RECUPERACAO,
            f"Não foi possível recuperar o robô automaticamente: {e}",
            plataforma=plataforma,
        )
        logger.exception("%sFalha ao criar/recriar instância do bot.", _job_tag(job_id))
        raise


def get_bot(job_id: str | None = None, plataforma: str = PLATFORM_MERCADOLIVRE):

    with _bot_lock:
        driver = _drivers.get(plataforma)
        bot = _bots.get(plataforma)
        driver_vivo = driver_esta_vivo(driver)
        bot_com_driver_valido = bot is not None and getattr(bot, "driver", None) is driver

        if not driver_vivo or not bot_com_driver_valido:
            logger.warning(
                "%sDriver indisponível/inválido para %s (driver_vivo=%s, bot_com_driver_valido=%s). Recriando bot.",
                _job_tag(job_id),
                plataforma,
                driver_vivo,
                bot_com_driver_valido,
            )
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    logger.warning(
                        "%sFalha ao encerrar driver inválido; liberando lock de profile de forma defensiva.",
                        _job_tag(job_id),
                    )
                    liberar_profile_em_uso(CHROME_PROFILE_DIR.resolve() / plataforma)
            _drivers[plataforma] = None
            _bots[plataforma] = None
            return criar_nova_instancia(job_id=job_id, plataforma=plataforma)

        logger.info("%sReusando instância atual do bot (%s) e sessão ativa do navegador.", _job_tag(job_id), plataforma)
        return bot


def reiniciar_bot(job_id: str | None = None, plataforma: str = PLATFORM_MERCADOLIVRE):

    with _bot_lock:
        logger.warning("%sReiniciando bot (%s) sob demanda.", _job_tag(job_id), plataforma)
        try:
            driver = _drivers.get(plataforma)
            if driver is not None:
                driver.quit()
                logger.info("%sDriver anterior encerrado com sucesso.", _job_tag(job_id))
        except Exception:
            logger.exception("%sFalha ao encerrar driver anterior durante reinício.", _job_tag(job_id))
            liberar_profile_em_uso(CHROME_PROFILE_DIR.resolve() / plataforma)

        _drivers[plataforma] = None
        _bots[plataforma] = None

        return criar_nova_instancia(job_id=job_id, plataforma=plataforma)
