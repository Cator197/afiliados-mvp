from pathlib import Path
import os
import shutil

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from config import (
    CHROME_BINARY_PATH,
    CHROME_DISPLAY,
    CHROME_HEADLESS,
    CHROME_PROFILE_DIR,
    CHROMEDRIVER_PATH,
    CHROME_USE_WEBDRIVER_MANAGER_FALLBACK,
)


LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"


def _resolver_caminho_chromedriver() -> str | None:
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH

    chromedriver_no_path = shutil.which("chromedriver")
    if chromedriver_no_path:
        return chromedriver_no_path

    return None


def _montar_options(profile_dir: Path) -> Options:
    options = Options()

    if CHROME_BINARY_PATH:
        options.binary_location = CHROME_BINARY_PATH

    # Abre como "app", com menos interface e menos chance de fechar por engano
    options.add_argument(f"--app={LINK_BUILDER_URL}")
    options.add_argument("--start-maximized")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Não força headless por padrão; permite ativar por configuração
    if CHROME_HEADLESS:
        options.add_argument("--headless=new")

    # Perfil persistente: mantém cookies, login e sessão quando possível
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    # Ajustes de compatibilidade para Linux/Ubuntu com perfil persistente
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--password-store=basic")

    # Ajustes para ficar menos "cara de automação"
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


def _criar_driver_com_fallback(options: Options):
    chromedriver_bin = _resolver_caminho_chromedriver()

    # Caminho recomendado para servidor: usar chromedriver instalado no sistema.
    if chromedriver_bin:
        return webdriver.Chrome(service=Service(chromedriver_bin), options=options)

    # Selenium Manager (Selenium 4.6+) como fallback sem acoplamento ao webdriver-manager.
    try:
        return webdriver.Chrome(options=options)
    except WebDriverException:
        if not CHROME_USE_WEBDRIVER_MANAGER_FALLBACK:
            raise

    # Último fallback opcional: webdriver-manager (pode depender de internet em runtime).
    from webdriver_manager.chrome import ChromeDriverManager

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )


def criar_driver():
    profile_dir = CHROME_PROFILE_DIR.resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Respeita DISPLAY já existente (Xvfb) e permite definir por configuração.
    if CHROME_DISPLAY and not os.getenv("DISPLAY"):
        os.environ["DISPLAY"] = CHROME_DISPLAY

    options = _montar_options(profile_dir)
    driver = _criar_driver_com_fallback(options)

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver
