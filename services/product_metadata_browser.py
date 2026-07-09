import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from config import (
    CHROME_BINARY_PATH,
    CHROME_DISPLAY,
    CHROMEDRIVER_PATH,
)
from services.browser_manager import build_worker_chrome_options


logger = logging.getLogger(__name__)
DEFAULT_METADATA_PROFILE_DIR = Path(r"C:\projetos\afiliados-mvp\data\chrome_profile_metadata")
LOCK_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket")


def _resolve_metadata_profile_dir() -> Path:
    configured = os.getenv("METADATA_CHROME_PROFILE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    return DEFAULT_METADATA_PROFILE_DIR.resolve()


def _resolve_chromedriver() -> str | None:
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH
    return None


def _build_options(profile_dir: Path):
    return build_worker_chrome_options(
        profile_dir=profile_dir,
        app_url="https://www.mercadolivre.com.br/",
        disable_infobars=False,
    )


def _list_running_chrome_processes() -> list[str]:
    commands = (["tasklist"], ["pgrep", "-a", "chrome"])
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            continue

        output = (result.stdout or "").splitlines()
        matches = [line.strip() for line in output if "chrome" in line.lower()]
        if matches:
            return matches

    return []


def _remove_profile_locks(profile_dir: Path) -> list[str]:
    removed: list[str] = []
    for filename in LOCK_FILES:
        lock_path = profile_dir / filename
        if not lock_path.exists():
            continue
        if lock_path.is_dir():
            shutil.rmtree(lock_path, ignore_errors=True)
        else:
            lock_path.unlink(missing_ok=True)
        removed.append(str(lock_path))

    return removed


def _start_driver(profile_dir: Path):
    options = _build_options(profile_dir)
    chromedriver = _resolve_chromedriver()
    if chromedriver:
        return webdriver.Chrome(service=Service(chromedriver), options=options)
    return webdriver.Chrome(options=options)


def create_metadata_driver():
    if CHROME_DISPLAY:
        os.environ["DISPLAY"] = CHROME_DISPLAY

    persistent_profile_dir = _resolve_metadata_profile_dir()
    persistent_profile_dir.mkdir(parents=True, exist_ok=True)

    running_chrome = _list_running_chrome_processes()
    if running_chrome:
        logger.warning("[METADATA] Processos Chrome abertos detectados: %s", running_chrome)
    else:
        logger.info("[METADATA] Nenhum processo Chrome aberto detectado antes de iniciar.")

    removed_locks = _remove_profile_locks(persistent_profile_dir)
    if removed_locks:
        logger.warning("[METADATA] Locks removidos do profile persistente: %s", removed_locks)
    else:
        logger.info("[METADATA] Nenhum lock detectado no profile persistente.")

    logger.info(
        "[METADATA] Tentando profile persistente... binary=%s profile=%s",
        CHROME_BINARY_PATH or "default",
        persistent_profile_dir,
    )

    try:
        driver = _start_driver(persistent_profile_dir)
        driver.set_page_load_timeout(40)
        logger.info("[METADATA] Driver Selenium iniciado com profile persistente: %s", persistent_profile_dir)
        return driver
    except Exception as exc:
        logger.exception("[METADATA] Falhou profile persistente... erro=%s", exc)

    temporary_profile_dir = Path(tempfile.mkdtemp(prefix="metadata_profile_"))
    logger.warning("[METADATA] Iniciando profile temporário... profile=%s", temporary_profile_dir)
    print("Faça login novamente no Mercado Livre pois este profile é temporário")

    driver = _start_driver(temporary_profile_dir)
    driver.set_page_load_timeout(40)
    logger.info("[METADATA] Driver Selenium iniciado com profile temporário: %s", temporary_profile_dir)
    return driver
