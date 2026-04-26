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
        method_used = None
        used_fallback = False

        # 1) Prioriza <meta itemprop="price"> dentro do preço principal.
        principal_meta_price = self.driver.find_elements(
            By.CSS_SELECTOR,
            "span.ui-pdp-price__part[itemprop='offers'] meta[itemprop='price']",
        )
        for element in principal_meta_price:
            try:
                content = (element.get_attribute("content") or "").strip()
                if content:
                    value = self._parse_price(content)
                    if value is not None:
                        method_used = "main_price_meta_content"
                        logger.info(
                            "[METADATA] valor_produto capturado: %.2f | método=%s | fallback=%s",
                            value,
                            method_used,
                            used_fallback,
                        )
                        return value
            except StaleElementReferenceException:
                continue

        # 2) Fallback no container do preço principal (fraction + cents).
        principal_containers = self.driver.find_elements(
            By.CSS_SELECTOR,
            "span.ui-pdp-price__part[itemprop='offers']",
        )
        for container in principal_containers:
            try:
                if not container.is_displayed():
                    continue
                value = self._extract_from_fraction_and_cents(container)
                if value is not None:
                    method_used = "main_price_container_fraction_cents"
                    logger.info(
                        "[METADATA] valor_produto capturado: %.2f | método=%s | fallback=%s",
                        value,
                        method_used,
                        used_fallback,
                    )
                    return value
            except StaleElementReferenceException:
                continue

        # 3) Alternativas de preço principal, ignorando preço antigo/riscado.
        alternative_elements = self.driver.find_elements(
            By.CSS_SELECTOR,
            "span.andes-money-amount.ui-pdp-price__part",
        )
        for element in alternative_elements:
            try:
                if not element.is_displayed() or self._is_ignored_price_element(element):
                    continue
                value = self._extract_from_fraction_and_cents(element)
                if value is not None:
                    method_used = "alternative_main_price_filtered"
                    logger.info(
                        "[METADATA] valor_produto capturado: %.2f | método=%s | fallback=%s",
                        value,
                        method_used,
                        used_fallback,
                    )
                    return value
            except StaleElementReferenceException:
                continue

        # 4) Fallback final: menor valor positivo plausível acima de 1.
        fallback_value = self._fallback_lowest_visible_price()
        if fallback_value is not None:
            method_used = "fallback_lowest_visible_price"
            used_fallback = True
            logger.info(
                "[METADATA] valor_produto capturado: %.2f | método=%s | fallback=%s",
                fallback_value,
                method_used,
                used_fallback,
            )
            return fallback_value

        logger.warning(
            "[METADATA] Não foi possível capturar valor_produto | método=%s | fallback=%s",
            method_used,
            used_fallback,
        )
        return None

    def _parse_price(self, raw_value: str):
        if raw_value is None:
            return None

        cleaned = re.sub(r"[^0-9,\.]", "", raw_value).strip()
        if not cleaned:
            return None

        # Se tem vírgula e ponto, assume vírgula como milhar e ponto como decimal.
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        # Se só vírgula, assume vírgula decimal.
        elif "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")

        try:
            value = float(cleaned)
        except ValueError:
            return None

        if value <= 0:
            return None
        return value

    def _extract_from_fraction_and_cents(self, container):
        fraction_raw = ""
        cents_raw = ""

        fraction_elements = container.find_elements(By.CSS_SELECTOR, "span.andes-money-amount__fraction")
        if fraction_elements:
            fraction_raw = (fraction_elements[0].text or "").strip()
        cents_elements = container.find_elements(By.CSS_SELECTOR, "span.andes-money-amount__cents")
        if cents_elements:
            cents_raw = (cents_elements[0].text or "").strip()

        fraction_digits = re.sub(r"[^0-9]", "", fraction_raw)
        if not fraction_digits:
            return None

        cents_digits = re.sub(r"[^0-9]", "", cents_raw) if cents_raw else "00"
        cents_digits = cents_digits[:2].ljust(2, "0")
        return self._parse_price(f"{fraction_digits}.{cents_digits}")

    def _is_ignored_price_element(self, element):
        ignored_xpath = (
            "ancestor::s[contains(@class, 'ui-pdp-price__original-value')]"
            " | ancestor::*[contains(@class, 'original-value')]"
            " | ancestor::*[contains(@class, 'previous-price')]"
            " | ancestor::*[contains(@class, 'discount')]"
        )
        ignored_ancestors = element.find_elements(By.XPATH, ignored_xpath)
        return bool(ignored_ancestors)

    def _fallback_lowest_visible_price(self):
        candidates = []
        elements = self.driver.find_elements(By.CSS_SELECTOR, "span.andes-money-amount")
        for element in elements:
            try:
                if not element.is_displayed() or self._is_ignored_price_element(element):
                    continue
                value = self._extract_from_fraction_and_cents(element)
                if value is not None and value > 1:
                    candidates.append(value)
            except StaleElementReferenceException:
                continue

        if not candidates:
            return None
        return min(candidates)

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
