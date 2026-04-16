import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"
logger = logging.getLogger(__name__)


class LoginNecessarioError(Exception):
    """Erro controlado quando o portal exige login manual."""


class FluxoGeracaoLinkError(Exception):
    """Erro controlado para etapas do fluxo de geração de link."""

    def __init__(self, mensagem: str, etapa: str, retryable: bool = False):
        super().__init__(mensagem)
        self.etapa = etapa
        self.retryable = retryable


URL_INPUT_SELECTORS = [
    (By.ID, "url-0"),
    (By.CSS_SELECTOR, "input[id^='url-']"),
    (By.CSS_SELECTOR, "input[name='url']"),
    (By.XPATH, "//input[contains(@placeholder,'URL')]"),
]

GERAR_BUTTON_SELECTORS = [
    (By.XPATH, "//button[.//span[normalize-space()='Gerar']]"),
    (By.XPATH, "//button[normalize-space()='Gerar']"),
    (By.XPATH, "//button[contains(.,'Gerar link')]"),
    (By.CSS_SELECTOR, "button[data-testid*='generate']"),
]

RESULTADO_LINK_SELECTORS = [
    (By.ID, "textfield-copyLink-1"),
    (By.CSS_SELECTOR, "input[id^='textfield-copyLink-']"),
    (By.CSS_SELECTOR, "input[id*='copyLink']"),
    (By.CSS_SELECTOR, "input[readonly][value^='http']"),
]


class AfiliadoBot:
    def __init__(self, driver, timeout=20, atualizar_status=None):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)
        self.atualizar_status = atualizar_status

    def abrir_portal(self):
        logger.info("[BOT FLOW] Etapa: abrir página do portal.")
        self.driver.get(LINK_BUILDER_URL)
        self._aguardar_login_ou_portal()

    def _esta_em_tela_login(self) -> bool:
        url_atual = (self.driver.current_url or "").lower()
        if "login" in url_atual or "registration" in url_atual:
            return True

        seletores_login = [
            (By.CSS_SELECTOR, "input[name='user_id']"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.XPATH, "//button[contains(., 'Entrar')]"),
            (By.XPATH, "//button[contains(., 'Continuar')]"),
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

    def _aguardar_login_ou_portal(self):
        def _portal_ou_login(driver):
            if self._esta_em_tela_login():
                return "login"
            if self._portal_tem_campo_url():
                return "portal"
            url_atual = (driver.current_url or "").lower()
            if "mercadolivre.com.br" in url_atual:
                return "dominio"
            return False

        resultado = self.wait.until(_portal_ou_login)
        if resultado == "login":
            if callable(self.atualizar_status):
                self.atualizar_status(
                    "aguardando_login_manual",
                    "Aguardando login manual no navegador",
                )
            logger.warning("[BOT FLOW] Aguardando login manual no navegador.")
        return resultado

    def _wait_first_element(
        self,
        selectors,
        etapa: str,
        clickable: bool = False,
        timeout_message: str | None = None,
    ):
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

    def preparar_login_manual(self):
        logger.info(
            "[BOT FLOW] Login manual necessário: mantendo Chrome do Selenium aberto no portal para autenticação via VNC."
        )
        self.abrir_portal()

    def esta_logado(self) -> bool:
        logger.info("[BOT FLOW] Etapa: verificar se sessão está autenticada.")
        self.driver.get(LINK_BUILDER_URL)
        self._aguardar_login_ou_portal()
        return not self._esta_em_tela_login()

    def portal_pronto(self) -> bool:
        try:
            logger.info("[BOT FLOW] Etapa: validar login/sessão no portal.")
            self.driver.get(LINK_BUILDER_URL)
            if self._esta_em_tela_login():
                logger.warning("[BOT FLOW] Login necessário detectado ao validar sessão.")
                return False

            self._wait_first_element(
                selectors=URL_INPUT_SELECTORS,
                etapa="validar campo da URL no portal",
            )
            logger.info("[BOT FLOW] Portal pronto e campo URL disponível.")
            return True
        except Exception:
            logger.exception("[BOT FLOW] Falha na etapa de validação de login/sessão.")
            return False

    def garantir_portal_pronto(self):
        self.abrir_portal()

        if self.esta_logado() and self.portal_pronto():
            return

        logger.warning("[BOT FLOW] Aguardando login manual no navegador.")
        if callable(self.atualizar_status):
            self.atualizar_status(
                "aguardando_login_manual",
                "Aguardando login manual no navegador",
            )

    def gerar_link(self, url_produto: str) -> str:
        etapa = "início"
        self.garantir_portal_pronto()

        if not self.esta_logado():
            logger.warning("[BOT FLOW] Login manual pendente antes da geração de link.")
            raise LoginNecessarioError("LOGIN_MANUAL_NECESSARIO")

        try:
            etapa = "localizar campo"
            logger.info("[BOT FLOW] Etapa: localizar campo de URL.")
            campo_url = self._wait_first_element(
                selectors=URL_INPUT_SELECTORS,
                etapa="campo da URL",
                timeout_message="Campo da URL não encontrado no portal de afiliados.",
            )

            etapa = "preencher URL"
            logger.info("[BOT FLOW] Etapa: preencher URL do produto.")
            campo_url.clear()
            campo_url.send_keys(url_produto)

            etapa = "clicar botão gerar"
            logger.info("[BOT FLOW] Etapa: clicar no botão gerar.")
            botao_gerar = self._wait_first_element(
                selectors=GERAR_BUTTON_SELECTORS,
                etapa="botão gerar",
                clickable=True,
                timeout_message="Botão gerar não encontrado no portal de afiliados.",
            )
            botao_gerar.click()

            etapa = "aguardar resultado"
            logger.info("[BOT FLOW] Etapa: aguardar resultado do link.")

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

            etapa = "capturar link final"
            try:
                link_final = self.wait.until(link_valido)
            except TimeoutException as exc:
                raise FluxoGeracaoLinkError(
                    "Timeout ao aguardar resultado da geração do link.",
                    etapa="aguardar resultado",
                    retryable=True,
                ) from exc

            if not link_final:
                raise FluxoGeracaoLinkError(
                    "Link final não encontrado após clicar em gerar.",
                    etapa="capturar link final",
                    retryable=True,
                )

            logger.info("[BOT FLOW] Etapa: capturar link final concluída.")
            return link_final
        except FluxoGeracaoLinkError:
            raise
        except TimeoutException as exc:
            mensagens = {
                "localizar campo": "Campo da URL não encontrado no portal de afiliados.",
                "clicar botão gerar": "Botão gerar não encontrado no portal de afiliados.",
            }
            raise FluxoGeracaoLinkError(
                mensagens.get(etapa, f"Timeout na etapa '{etapa}' da geração de link."),
                etapa=etapa,
                retryable=True,
            ) from exc
        except Exception:
            logger.exception("[BOT FLOW] Falha na etapa '%s' da geração de link.", etapa)
            raise
