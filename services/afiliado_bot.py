import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"
logger = logging.getLogger(__name__)


class LoginNecessarioError(Exception):
    """Erro controlado quando o portal exige login manual."""


class AfiliadoBot:
    def __init__(self, driver, timeout=20):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def abrir_portal(self):
        logger.info("[BOT FLOW] Etapa: abrir página do portal.")
        self.driver.get(LINK_BUILDER_URL)

    def preparar_login_manual(self):
        logger.info(
            "[BOT FLOW] Login manual necessário: mantendo Chrome do Selenium aberto no portal para autenticação via VNC."
        )
        self.abrir_portal()

    def portal_pronto(self) -> bool:
        try:
            logger.info("[BOT FLOW] Etapa: validar login/sessão no portal.")
            self.driver.get(LINK_BUILDER_URL)
            self.wait.until(
                EC.presence_of_element_located((By.ID, "url-0"))
            )
            logger.info("[BOT FLOW] Portal pronto e campo URL disponível.")
            return True
        except Exception:
            logger.exception("[BOT FLOW] Falha na etapa de validação de login/sessão.")
            return False

    def garantir_portal_pronto(self):
        self.abrir_portal()

        if self.portal_pronto():
            return

        self.preparar_login_manual()
        raise LoginNecessarioError(
            "Portal do afiliado exige login manual no perfil atual do Chrome."
        )

    def gerar_link(self, url_produto: str) -> str:
        etapa = "início"
        self.garantir_portal_pronto()

        try:
            etapa = "localizar campo"
            logger.info("[BOT FLOW] Etapa: localizar campo de URL.")
            campo_url = self.wait.until(
                EC.presence_of_element_located((By.ID, "url-0"))
            )

            etapa = "preencher URL"
            logger.info("[BOT FLOW] Etapa: preencher URL do produto.")
            campo_url.clear()
            campo_url.send_keys(url_produto)

            etapa = "clicar botão gerar"
            logger.info("[BOT FLOW] Etapa: clicar no botão gerar.")
            botao_gerar = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[normalize-space()='Gerar']]")
                )
            )
            botao_gerar.click()

            etapa = "aguardar resultado"
            logger.info("[BOT FLOW] Etapa: aguardar resultado do link.")

            def link_valido(driver):
                elemento = driver.find_element(By.ID, "textfield-copyLink-1")
                valor = elemento.get_attribute("value")
                if not valor:
                    valor = elemento.text.strip()

                if valor and valor.startswith("http") and valor != url_produto:
                    return valor
                return False

            etapa = "capturar link final"
            link_final = self.wait.until(link_valido)
            logger.info("[BOT FLOW] Etapa: capturar link final concluída.")
            return link_final
        except Exception:
            logger.exception("[BOT FLOW] Falha na etapa '%s' da geração de link.", etapa)
            raise
