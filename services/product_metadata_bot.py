import logging
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


logger = logging.getLogger(__name__)


class ProductMetadataBot:
    def __init__(self, driver, timeout: int = 20):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def _first_visible_text(self, selectors):
        for by, value in selectors:
            elements = self.driver.find_elements(by, value)
            for element in elements:
                try:
                    if element.is_displayed():
                        text = (element.text or "").strip()
                        if text:
                            return text
                except StaleElementReferenceException:
                    continue
        return None

    def _first_visible_image_src(self, selectors):
        for by, value in selectors:
            elements = self.driver.find_elements(by, value)
            for element in elements:
                try:
                    if element.is_displayed():
                        src = (element.get_attribute("src") or "").strip()
                        if src:
                            return src
                except StaleElementReferenceException:
                    continue
        return None

    def _extract_percentual_comissao(self):
        ganhos_selectors = [
            (By.XPATH, "//*[contains(translate(normalize-space(.), 'ganhos', 'GANHOS'), 'GANHOS') and contains(., '%')]"),
            (By.XPATH, "//*[contains(., 'GANHOS') and contains(., '%')]"),
        ]
        ganhos_text = self._first_visible_text(ganhos_selectors)
        if not ganhos_text:
            return None

        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", ganhos_text)
        if not match:
            return None

        return float(match.group(1).replace(",", "."))

    def _extract_valor_produto(self):
        selectors = [
            (By.CSS_SELECTOR, "span.andes-money-amount__fraction"),
        ]
        raw = self._first_visible_text(selectors)
        if not raw:
            return None

        digits_only = re.sub(r"[^0-9]", "", raw)
        if not digits_only:
            return None

        return float(digits_only)

    def extrair_metadados(self, url_original: str) -> dict:
        logger.info("[METADATA] Abrindo URL original para extração: %s", url_original)
        self.driver.get(url_original)

        try:
            self.wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "h1.ui-pdp-title"))
        except TimeoutException as exc:
            raise RuntimeError("Timeout ao carregar página do produto.") from exc

        descricao = self._first_visible_text([(By.CSS_SELECTOR, "h1.ui-pdp-title")])
        foto_url = self._first_visible_image_src(
            [(By.CSS_SELECTOR, "img.ui-pdp-image.ui-pdp-gallery__figure__image")]
        )
        valor_produto = self._extract_valor_produto()
        percentual_comissao = self._extract_percentual_comissao()

        if valor_produto is None:
            raise RuntimeError("Não foi possível capturar o valor do produto.")
        if percentual_comissao is None:
            raise RuntimeError("Não foi possível capturar o percentual de comissão (GANHOS).")

        return {
            "descricao_item": descricao,
            "foto_item_url": foto_url,
            "valor_produto": valor_produto,
            "percentual_comissao": percentual_comissao,
        }
