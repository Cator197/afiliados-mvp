import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from config import CHROME_BINARY_PATH, CHROME_DISPLAY, CHROMEDRIVER_PATH, CHROME_PROFILE_DIR


logger = logging.getLogger(__name__)
METADATA_PROFILE_DIR = Path(CHROME_PROFILE_DIR).resolve() / "metadata"


def _resolve_chromedriver() -> str | None:
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH
    return None


def _build_options(profile_dir: Path) -> Options:
    options = Options()

    if CHROME_BINARY_PATH:
        options.binary_location = CHROME_BINARY_PATH

    options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


def create_metadata_driver():
    if CHROME_DISPLAY:
        import os
        os.environ["DISPLAY"] = CHROME_DISPLAY

    METADATA_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    options = _build_options(METADATA_PROFILE_DIR)

    chromedriver = _resolve_chromedriver()
    if chromedriver:
        driver = webdriver.Chrome(service=Service(chromedriver), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(40)
    logger.info("[METADATA] Driver Selenium iniciado com profile dedicado: %s", METADATA_PROFILE_DIR)
    return driver
