from pathlib import Path
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"


def criar_driver():
    profile_dir = Path("data/chrome_profile").resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    options = Options()

    # Abre como "app", com menos interface e menos chance de fechar por engano
    options.add_argument(f"--app={LINK_BUILDER_URL}")
    options.add_argument("--start-maximized")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Não força headless por padrão; permite ativar por configuração futura
    headless_mode = os.getenv("CHROME_HEADLESS", "").lower() in {"1", "true", "yes"}
    if headless_mode:
        options.add_argument("--headless=new")

    # Perfil persistente: mantém cookies, login e sessão quando possível
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    # Ajustes para ficar menos "cara de automação"
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver
