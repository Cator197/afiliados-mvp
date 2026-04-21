from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "afiliados.db"

SECRET_KEY = os.getenv("SECRET_KEY", "trocar_essa_chave_no_futuro")

# 127.0.0.1 permite apenas acesso local; 0.0.0.0 libera acesso externo (ex.: VPS)
# FLASK_HOST é priorizado para evitar conflito com variáveis globais de ambiente.
HOST = (os.getenv("FLASK_HOST") or os.getenv("HOST") or "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ADMIN_DEFAULT_USERNAME = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "123456")

CASHBACK_PERCENTUAL_PADRAO = 50.0

JOB_STATUS_NA_FILA = "na_fila"
JOB_STATUS_PROCESSANDO = "processando"
JOB_STATUS_CONCLUIDO = "concluido"
JOB_STATUS_ERRO = "erro"

LINK_STATUS_AGUARDANDO_VERIFICACAO = "aguardando_verificacao"
LINK_STATUS_COMPRA_CONFIRMADA = "compra_confirmada"
LINK_STATUS_COMPRA_NAO_CONFIRMADA = "compra_nao_confirmada"
LINK_STATUS_CASHBACK_PAGO = "cashback_pago"

DOMINIOS_PERMITIDOS = [
    "mercadolivre.com",
    "mercadolivre.com.br"
]

BOT_STATUS_OFFLINE = "offline"
BOT_STATUS_RECRIANDO = "recriando"
BOT_STATUS_ONLINE = "online"
BOT_STATUS_AGUARDANDO_LOGIN = "aguardando_login_manual"
BOT_STATUS_ERRO_RECUPERACAO = "erro_recuperacao"

WORKER_API_TOKEN = os.getenv("WORKER_API_TOKEN", "")
WORKER_ENABLED = os.getenv("WORKER_ENABLED", "true").lower() in {"1", "true", "yes"}
WORKER_ID = os.getenv("WORKER_ID", "local-worker").strip()
WORKER_POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5"))
WORKER_HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("WORKER_HEARTBEAT_INTERVAL_SECONDS", "15"))
WORKER_INACTIVE_THRESHOLD_SECONDS = int(os.getenv("WORKER_INACTIVE_THRESHOLD_SECONDS", "45"))
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "900"))
VPS_BASE_URL = os.getenv("VPS_BASE_URL", "").strip().rstrip("/")


# Selenium/Chrome runtime configuration (Ubuntu + Xvfb friendly)
CHROME_HEADLESS = os.getenv("CHROME_HEADLESS", "false").lower() in {"1", "true", "yes"}
CHROME_DISPLAY = os.getenv("CHROME_DISPLAY", "")
CHROME_BINARY_PATH = os.getenv("CHROME_BINARY_PATH", "").strip()
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "").strip()
CHROME_USE_WEBDRIVER_MANAGER_FALLBACK = os.getenv(
    "CHROME_USE_WEBDRIVER_MANAGER_FALLBACK",
    "false"
).lower() in {"1", "true", "yes"}
CHROME_PROFILE_DIR = Path(
    os.getenv("CHROME_PROFILE_DIR", str(DATA_DIR / "chrome_profile"))
).expanduser()
