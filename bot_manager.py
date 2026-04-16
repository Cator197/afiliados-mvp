import threading

from services.browser_manager import criar_driver
from services.afiliado_bot import AfiliadoBot, LoginNecessarioError
from config import (
    BOT_STATUS_OFFLINE,
    BOT_STATUS_RECRIANDO,
    BOT_STATUS_ONLINE,
    BOT_STATUS_AGUARDANDO_LOGIN,
    BOT_STATUS_ERRO_RECUPERACAO,
)


_driver = None
_bot = None
_bot_lock = threading.Lock()

_bot_status = BOT_STATUS_OFFLINE
_bot_message = "Bot ainda não inicializado."


def set_bot_status(status, message):
    global _bot_status, _bot_message
    _bot_status = status
    _bot_message = message
    print(f"[BOT STATUS] {status} - {message}")


def get_bot_status():
    return {
        "status": _bot_status,
        "message": _bot_message
    }


def driver_esta_vivo(driver) -> bool:
    if driver is None:
        return False

    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def criar_nova_instancia():
    global _driver, _bot

    try:
        set_bot_status(BOT_STATUS_RECRIANDO, "Recriando navegador do robô...")

        _driver = criar_driver()
        _bot = AfiliadoBot(_driver)

        set_bot_status(BOT_STATUS_AGUARDANDO_LOGIN, "Verificando sessão do Mercado Livre...")

        try:
            _bot.garantir_portal_pronto()
        except LoginNecessarioError:
            set_bot_status(
                BOT_STATUS_AGUARDANDO_LOGIN,
                "Chrome aberto com perfil persistente, mas login manual é necessário."
            )
            raise

        set_bot_status(BOT_STATUS_ONLINE, "Robô pronto para uso.")
        return _bot

    except Exception as e:
        set_bot_status(
            BOT_STATUS_ERRO_RECUPERACAO,
            f"Não foi possível recuperar o robô automaticamente: {e}"
        )
        raise


def get_bot():
    global _bot, _driver

    with _bot_lock:
        if not driver_esta_vivo(_driver) or _bot is None:
            print("[BOT] Driver indisponível. Recriando...")
            return criar_nova_instancia()

        return _bot


def reiniciar_bot():
    global _driver, _bot

    with _bot_lock:
        try:
            if _driver is not None and driver_esta_vivo(_driver):
                _driver.quit()
        except Exception:
            pass

        _driver = None
        _bot = None

        return criar_nova_instancia()
