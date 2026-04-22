import unittest
from unittest.mock import MagicMock, patch

from services.shopee_bot import GERAR_BUTTON_SELECTORS, URL_INPUT_SELECTORS, ShopeeBot


class ShopeeBotSelectorsTests(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.bot = ShopeeBot(self.driver)

    def test_url_input_selectors_prioritize_textarea(self):
        self.assertEqual(URL_INPUT_SELECTORS[0][1], "#customLink_original_url textarea")
        self.assertEqual(URL_INPUT_SELECTORS[1][1], ".custom-textarea textarea")

    def test_gerar_button_selectors_include_obter_link_priority(self):
        self.assertIn("Obter link", GERAR_BUTTON_SELECTORS[0][1])
        self.assertIn("Obter link", GERAR_BUTTON_SELECTORS[1][1])

    @patch.object(ShopeeBot, "garantir_portal_pronto")
    @patch.object(ShopeeBot, "esta_logado", return_value=True)
    def test_gerar_link_preenche_textarea_e_clica_botao(
        self,
        _mock_esta_logado,
        _mock_garantir_portal_pronto,
    ):
        textarea = MagicMock()
        button = MagicMock()
        expected_link = "https://afiliado.shopee/link"

        def _wait_first_element_side_effect(*args, **kwargs):
            etapa = kwargs.get("etapa")
            if etapa == "campo da URL Shopee":
                return textarea
            if etapa == "botão gerar Shopee":
                return button
            raise AssertionError(f"Etapa inesperada: {etapa}")

        self.bot._wait_first_element = MagicMock(side_effect=_wait_first_element_side_effect)
        self.bot.wait = MagicMock()
        self.bot.wait.until.return_value = expected_link

        generated = self.bot.gerar_link("https://shopee.com.br/item")

        textarea.clear.assert_called_once()
        textarea.send_keys.assert_called_once_with("https://shopee.com.br/item")
        button.click.assert_called_once()
        self.assertEqual(generated, expected_link)


if __name__ == "__main__":
    unittest.main()
