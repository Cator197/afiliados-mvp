from pathlib import Path
import os
import shutil
import logging

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
logger = logging.getLogger(__name__)
CHROME_WINDOW_SIZE = "1280,720"


def _resolver_caminho_chrome() -> str | None:
    if CHROME_BINARY_PATH:
        caminho_configurado = Path(CHROME_BINARY_PATH).expanduser()
        if caminho_configurado.exists():
            return str(caminho_configurado)
        logger.warning(
            "CHROME_BINARY_PATH configurado, mas não encontrado: %s",
            CHROME_BINARY_PATH,
        )

    candidatos = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for caminho in candidatos:
        if caminho:
            return caminho

    return None


def _resolver_caminho_chromedriver() -> str | None:
    if CHROMEDRIVER_PATH:
        return CHROMEDRIVER_PATH

    chromedriver_no_path = shutil.which("chromedriver")
    if chromedriver_no_path:
        return chromedriver_no_path

    return None


def _montar_options(profile_dir: Path) -> Options:
    options = Options()
    chrome_bin = _resolver_caminho_chrome()

    if chrome_bin:
        options.binary_location = chrome_bin

    # Abre como "app", com menos interface e menos chance de fechar por engano
    options.add_argument(f"--app={LINK_BUILDER_URL}")
    options.add_argument(f"--window-size={CHROME_WINDOW_SIZE}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-default-apps")

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
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
        },
    )

    return options


def _criar_driver_com_fallback(options: Options):
    chromedriver_bin = _resolver_caminho_chromedriver()

    # Caminho recomendado para servidor: usar chromedriver instalado no sistema.
    if chromedriver_bin:
        logger.info("Subindo ChromeDriver pelo caminho explícito: %s", chromedriver_bin)
        return webdriver.Chrome(service=Service(chromedriver_bin), options=options)

    # Selenium Manager (Selenium 4.6+) como fallback sem acoplamento ao webdriver-manager.
    try:
        logger.info("Subindo ChromeDriver via Selenium Manager.")
        return webdriver.Chrome(options=options)
    except WebDriverException:
        if not CHROME_USE_WEBDRIVER_MANAGER_FALLBACK:
            raise

    # Último fallback opcional: webdriver-manager (pode depender de internet em runtime).
    from webdriver_manager.chrome import ChromeDriverManager

    logger.warning("Usando webdriver-manager como último fallback para subir o ChromeDriver.")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )


def criar_driver():
    profile_dir = CHROME_PROFILE_DIR.resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    chromedriver_bin = _resolver_caminho_chromedriver()
    chrome_bin = _resolver_caminho_chrome()

    # Em VPS com Xvfb/VNC, prioriza DISPLAY configurado do robô para garantir navegador visível.
    if CHROME_DISPLAY:
        os.environ["DISPLAY"] = CHROME_DISPLAY

    logger.info(
        "Inicializando Selenium otimizado: profile_dir=%s | display=%s | chrome_bin=%s | chromedriver=%s | headless=%s | window_size=%s | flags_otimizadas=%s",
        profile_dir,
        os.getenv("DISPLAY"),
        chrome_bin,
        chromedriver_bin or "selenium-manager/fallback",
        CHROME_HEADLESS,
        CHROME_WINDOW_SIZE,
        True,
    )

    options = _montar_options(profile_dir)
    argumentos = options.arguments or []
    logger.info(
        "Chrome binary_location configurado no Selenium: %s | argumentos=%s",
        options.binary_location or "não configurado (Selenium Manager decide)",
        argumentos,
    )
    try:
        driver = _criar_driver_com_fallback(options)
    except Exception:
        logger.exception("Falha ao subir o driver Chrome/Selenium.")
        raise

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    logger.info("Driver Chrome/Selenium inicializado com sucesso.")

    return driver
