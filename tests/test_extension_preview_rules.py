import unittest
from unittest.mock import patch

from services.extension_service import parse_price_for_preview
import config


class ExtensionPreviewRulesTests(unittest.TestCase):
    def test_parse_price_for_preview_variants(self):
        self.assertEqual(parse_price_for_preview(419.27), 419.27)
        self.assertEqual(parse_price_for_preview("419,27"), 419.27)
        self.assertEqual(parse_price_for_preview("R$ 419,27"), 419.27)
        self.assertEqual(parse_price_for_preview("1.299,90"), 1299.9)
        self.assertIsNone(parse_price_for_preview("abc"))
        self.assertIsNone(parse_price_for_preview("-10"))
        self.assertIsNone(parse_price_for_preview("1000001"))

    @patch.dict('os.environ', {}, clear=False)
    def test_default_percent_constant_is_bounded(self):
        self.assertGreaterEqual(config.MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT, 0)
        self.assertLessEqual(config.MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT, 20)


if __name__ == "__main__":
    unittest.main()
