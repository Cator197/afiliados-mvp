import logging

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from services.afiliado_bot import FluxoGeracaoLinkError, LoginNecessarioError


SHOPEE_AFFILIATE_URL = "https://affiliate.shopee.com.br/offer/custom_link"
logger = logging.getLogger(__name__)

URL_INPUT_SELECTORS = [
    (By.CSS_SELECTOR, "input[placeholder*='cole']"),
    (By.CSS_SELECTOR, "input[placeholder*='link']"),
    (By.CSS_SELECTOR, "input[type='url']"),
    (By.XPATH, "//input[contains(@placeholder,'URL') or contains(@placeholder,'Link') or contains(@placeholder,'link')]"),
]

GERAR_BUTTON_SELECTORS = [
    (By.XPATH, "//button[contains(.,'Gerar') or contains(.,'Criar') or contains(.,'Generate') or contains(.,'Create')]"),
    (By.CSS_SELECTOR, "button[type='submit']"),
]

RESULTADO_LINK_SELECTORS = [
    (By.CSS_SELECTOR, "input[readonly][value^='http']"),
    (By.CSS_SELECTOR, "input[value*='shopee']"),
    (By.XPATH, "//input[contains(@value,'http') and (contains(@value,'shopee') or contains(@value,'aff'))]"),
]


class ShopeeBot:
    def __init__(self, driver, timeout=15, atualizar_status=None):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)
        self.atualizar_status = atualizar_status
        self._aguardando_login_manual = False

    def _set_aguardando_login_manual(self, aguardando: bool):
        self._aguardando_login_manual = aguardando

    def _esta_em_tela_login(self) -> bool:
        url_atual = (self.driver.current_url or "").lower()
        if "login" in url_atual or "signin" in url_atual:
            return True

        seletores_login = [
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.CSS_SELECTOR, "input[name='loginKey']"),
            (By.XPATH, "//button[contains(., 'Entrar') or contains(., 'Login')]")
        ]
        for by, value in seletores_login:
            if self.driver.find_elements(by, value):
                return True
        return False

    def _portal_tem_campo_url(self) -> bool:
        for by, value in URL_INPUT_SELECTORS:
            elementos = self.driver.find_elements(by, value)
            for elemento in elementos:
                try:
                    if elemento.is_displayed():
                        return True
                except StaleElementReferenceException:
                    continue
        return False

    def _wait_first_element(self, selectors, etapa: str, clickable: bool = False, timeout_message: str | None = None):
        def _resolver(driver):
            for by, value in selectors:
                elementos = driver.find_elements(by, value)
                for elemento in elementos:
                    try:
                        if clickable:
                            if elemento.is_displayed() and elemento.is_enabled():
                                return elemento
                        elif elemento.is_displayed():
                            return elemento
                    except StaleElementReferenceException:
                        continue
            return False

        try:
            return self.wait.until(_resolver)
        except TimeoutException as exc:
            raise FluxoGeracaoLinkError(
                timeout_message or f"Timeout na etapa '{etapa}'.",
                etapa=etapa,
                retryable=True,
            ) from exc

    def abrir_portal(self):
        if self._aguardando_login_manual:
            return "login"
        logger.info("[BOT SHOPEE] Abrindo portal de afiliados.")
        self.driver.get(SHOPEE_AFFILIATE_URL)
        if self._esta_em_tela_login():
            self._set_aguardando_login_manual(True)
            if callable(self.atualizar_status):
                self.atualizar_status("aguardando_login_manual", "Aguardando login manual Shopee no navegador")
            return "login"
        self._set_aguardando_login_manual(False)
        return "portal"

    def preparar_login_manual(self):
        self.abrir_portal()

    def esta_logado(self, force_check: bool = False, passive_check: bool = False) -> bool:
        if self._aguardando_login_manual and not (force_check or passive_check):
            return False

        if passive_check:
            autenticado = not self._esta_em_tela_login()
            if autenticado:
                self._set_aguardando_login_manual(False)
            return autenticado

        self.driver.get(SHOPEE_AFFILIATE_URL)
        autenticado = not self._esta_em_tela_login()
        if autenticado:
            self._set_aguardando_login_manual(False)
        else:
            self._set_aguardando_login_manual(True)
        return autenticado

    def portal_pronto(self, force_check: bool = False, passive_check: bool = False) -> bool:
        if self._aguardando_login_manual and not (force_check or passive_check):
            return False

        if passive_check:
            return self._portal_tem_campo_url() and not self._esta_em_tela_login()

        self.driver.get(SHOPEE_AFFILIATE_URL)
        if self._esta_em_tela_login():
            self._set_aguardando_login_manual(True)
            return False

        self._wait_first_element(
            selectors=URL_INPUT_SELECTORS,
            etapa="validar campo da URL no portal Shopee",
            timeout_message="Campo da URL não encontrado no portal de afiliados da Shopee.",
        )
        self._set_aguardando_login_manual(False)
        return True

    def garantir_portal_pronto(self):
        self.abrir_portal()
        if self.esta_logado() and self.portal_pronto():
            return
        self._set_aguardando_login_manual(True)
        if callable(self.atualizar_status):
            self.atualizar_status("aguardando_login_manual", "Aguardando login manual Shopee no navegador")

    def gerar_link(self, url_produto: str) -> str:
        self.garantir_portal_pronto()

        if not self.esta_logado():
            raise LoginNecessarioError("LOGIN_MANUAL_NECESSARIO")

        campo_url = self._wait_first_element(
            selectors=URL_INPUT_SELECTORS,
            etapa="campo da URL Shopee",
            timeout_message="Campo da URL não encontrado no portal de afiliados da Shopee.",
        )
        campo_url.clear()
        campo_url.send_keys(url_produto)

        botao_gerar = self._wait_first_element(
            selectors=GERAR_BUTTON_SELECTORS,
            etapa="botão gerar Shopee",
            clickable=True,
            timeout_message="Botão de gerar não encontrado no portal de afiliados da Shopee.",
        )
        botao_gerar.click()

        def link_valido(driver):
            for by, value in RESULTADO_LINK_SELECTORS:
                elementos = driver.find_elements(by, value)
                for elemento in elementos:
                    try:
                        valor = (elemento.get_attribute("value") or "").strip()
                        if not valor:
                            valor = (elemento.text or "").strip()
                    except StaleElementReferenceException:
                        continue

                    if valor and valor.startswith("http") and valor != url_produto:
                        return valor
            return False

        try:
            return self.wait.until(link_valido)
        except TimeoutException as exc:
            raise FluxoGeracaoLinkError(
                "Falha ao gerar link no portal da Shopee.",
                etapa="aguardar resultado Shopee",
                retryable=True,
            ) from exc
