import unittest
from unittest.mock import patch

import queue_manager


class FakeBot:
    def __init__(self, link=None, exc=None):
        self.link = link
        self.exc = exc

    def gerar_link(self, _url):
        if self.exc:
            raise self.exc
        return self.link


class WorkerPlatformRoutingTests(unittest.TestCase):
    def _job(self, plataforma: str):
        return {
            "job_id": f"job-{plataforma}",
            "usuario_id": 1,
            "url_original": "https://example.com/item",
            "plataforma": plataforma,
        }

    @patch("queue_manager.create_link_gerado")
    @patch("queue_manager.update_job_status")
    @patch("queue_manager.get_bot")
    def test_routes_mercadolivre_to_mercadolivre_bot(self, mock_get_bot, _mock_update, _mock_link):
        mock_get_bot.return_value = FakeBot(link="https://meli.afiliado")

        queue_manager.process_job(self._job("mercadolivre"))

        mock_get_bot.assert_called_with(job_id="job-mercadolivre", plataforma="mercadolivre")

    @patch("queue_manager.create_link_gerado")
    @patch("queue_manager.update_job_status")
    @patch("queue_manager.get_bot")
    def test_shopee_is_controlled_error(self, mock_get_bot, mock_update, mock_link):
        queue_manager.process_job(self._job("shopee"))

        mock_get_bot.assert_not_called()
        mock_link.assert_not_called()
        self.assertEqual(mock_update.call_args_list[-1].kwargs["status"], "erro")

    @patch("queue_manager.create_link_gerado")
    @patch("queue_manager.update_job_status")
    @patch("queue_manager.get_bot")
    def test_unknown_platform_is_controlled_error(self, mock_get_bot, mock_update, mock_link):
        queue_manager.process_job(self._job("desconhecida"))

        mock_get_bot.assert_not_called()
        mock_link.assert_not_called()
        self.assertEqual(mock_update.call_args_list[-1].kwargs["status"], "erro")
        self.assertIn("não suportada", mock_update.call_args_list[-1].kwargs["mensagem_erro"])

if __name__ == "__main__":
    unittest.main()
