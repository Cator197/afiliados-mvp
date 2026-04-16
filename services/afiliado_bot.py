from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"


class LoginNecessarioError(Exception):
    """Erro controlado quando o portal exige login manual."""


class AfiliadoBot:
    def __init__(self, driver, timeout=20):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def abrir_portal(self):
        self.driver.get(LINK_BUILDER_URL)

    def portal_pronto(self) -> bool:
        try:
            self.driver.get(LINK_BUILDER_URL)
            self.wait.until(
                EC.presence_of_element_located((By.ID, "url-0"))
            )
            return True
        except Exception:
            return False

    def garantir_portal_pronto(self):
        self.abrir_portal()

        if self.portal_pronto():
            return

        raise LoginNecessarioError(
            "Portal do afiliado exige login manual no perfil atual do Chrome."
        )

    def gerar_link(self, url_produto: str) -> str:
        self.garantir_portal_pronto()

        campo_url = self.wait.until(
            EC.presence_of_element_located((By.ID, "url-0"))
        )
        campo_url.clear()
        campo_url.send_keys(url_produto)

        botao_gerar = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[normalize-space()='Gerar']]")
            )
        )
        botao_gerar.click()

        def link_valido(driver):
            elemento = driver.find_element(By.ID, "textfield-copyLink-1")
            valor = elemento.get_attribute("value")
            if not valor:
                valor = elemento.text.strip()

            if valor and valor.startswith("http") and valor != url_produto:
                return valor
            return False

        return self.wait.until(link_valido)
