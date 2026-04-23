from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "afiliados.db"


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: str = "false") -> bool:
    return _env_str(name, default).lower() in {"1", "true", "yes", "on"}


APP_ENV = (_env_str("APP_ENV") or _env_str("FLASK_ENV") or _env_str("ENV") or "development").lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

SECRET_KEY = _env_str("SECRET_KEY")

# 127.0.0.1 permite apenas acesso local; 0.0.0.0 libera acesso externo (ex.: VPS)
# FLASK_HOST é priorizado para evitar conflito com variáveis globais de ambiente.
HOST = (_env_str("FLASK_HOST") or _env_str("HOST") or "0.0.0.0").strip() or "0.0.0.0"
PORT = int(_env_str("PORT", "5000"))
DEBUG = _env_bool("DEBUG", "false")

# Cookies de sessão: em produção, o cookie deve trafegar apenas em HTTPS.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True if IS_PRODUCTION else _env_bool("SESSION_COOKIE_SECURE", "false")
SESSION_LIFETIME_MINUTES = int(_env_str("SESSION_LIFETIME_MINUTES", "480"))

ADMIN_DEFAULT_USERNAME = _env_str("ADMIN_DEFAULT_USERNAME")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "")

CASHBACK_PERCENTUAL_PADRAO = 50.0

JOB_STATUS_NA_FILA = "na_fila"
JOB_STATUS_PROCESSANDO = "processando"
JOB_STATUS_CONCLUIDO = "concluido"
JOB_STATUS_ERRO = "erro"

LINK_STATUS_AGUARDANDO_VERIFICACAO = "aguardando_verificacao"
LINK_STATUS_COMPRA_CONFIRMADA = "compra_confirmada"
LINK_STATUS_COMPRA_NAO_CONFIRMADA = "compra_nao_confirmada"
LINK_STATUS_CASHBACK_PAGO = "cashback_pago"

DOMINIOS_MERCADOLIVRE = [
    "mercadolivre.com",
    "mercadolivre.com.br"
]

DOMINIOS_SHOPEE = [
    "shopee.com",
    "shopee.com.br",
]

BOT_STATUS_OFFLINE = "offline"
BOT_STATUS_RECRIANDO = "recriando"
BOT_STATUS_ONLINE = "online"
BOT_STATUS_AGUARDANDO_LOGIN = "aguardando_login_manual"
BOT_STATUS_ERRO_RECUPERACAO = "erro_recuperacao"

WORKER_API_TOKEN = _env_str("WORKER_API_TOKEN")
WORKER_ENABLED = _env_bool("WORKER_ENABLED", "true")
WORKER_ID = _env_str("WORKER_ID", "local-worker")
WORKER_POLL_INTERVAL_SECONDS = int(_env_str("WORKER_POLL_INTERVAL_SECONDS", "5"))
WORKER_HEARTBEAT_INTERVAL_SECONDS = int(_env_str("WORKER_HEARTBEAT_INTERVAL_SECONDS", "15"))
WORKER_INACTIVE_THRESHOLD_SECONDS = int(_env_str("WORKER_INACTIVE_THRESHOLD_SECONDS", "45"))
JOB_TIMEOUT_SECONDS = int(_env_str("JOB_TIMEOUT_SECONDS", "900"))
VPS_BASE_URL = _env_str("VPS_BASE_URL").rstrip("/")


# Selenium/Chrome runtime configuration (Ubuntu + Xvfb friendly)
CHROME_HEADLESS = _env_bool("CHROME_HEADLESS", "false")
CHROME_DISPLAY = os.getenv("CHROME_DISPLAY", "")
CHROME_BINARY_PATH = _env_str("CHROME_BINARY_PATH")
CHROMEDRIVER_PATH = _env_str("CHROMEDRIVER_PATH")
CHROME_USE_WEBDRIVER_MANAGER_FALLBACK = _env_bool("CHROME_USE_WEBDRIVER_MANAGER_FALLBACK", "false")
CHROME_PROFILE_DIR = Path(
    _env_str("CHROME_PROFILE_DIR", str(DATA_DIR / "chrome_profile"))
).expanduser()


def validate_security_config():
    missing = []

    if not SECRET_KEY:
        missing.append("SECRET_KEY")

    if WORKER_ENABLED and not WORKER_API_TOKEN:
        missing.append("WORKER_API_TOKEN")

    if IS_PRODUCTION and missing:
        raise RuntimeError(
            "Configuração insegura para produção. Defina as variáveis obrigatórias: "
            + ", ".join(missing)
        )


validate_security_config()
