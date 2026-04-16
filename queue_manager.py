import queue
import threading
import logging
from datetime import datetime

from bot_manager import get_bot, reiniciar_bot
from config import (
    CASHBACK_PERCENTUAL_PADRAO,
    JOB_STATUS_PROCESSANDO,
    JOB_STATUS_CONCLUIDO,
    JOB_STATUS_ERRO,
    LINK_STATUS_AGUARDANDO_VERIFICACAO,
)
from repositories.jobs_repo import update_job_status
from repositories.links_repo import create_link_gerado
from services.afiliado_bot import LoginNecessarioError, FluxoGeracaoLinkError


job_queue = queue.Queue()
logger = logging.getLogger(__name__)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def enqueue_job(job_data: dict):
    job_id = job_data.get("job_id", "desconhecido")
    logger.info("[JOB %s] Enfileirando job.", job_id)
    job_queue.put(job_data)
    logger.info("[JOB %s] Job enfileirado com sucesso.", job_id)


def _update_job_status_com_log(job_id: str, status: str, **kwargs):
    logger.info("[JOB %s] Alterando status para '%s'.", job_id, status)
    update_job_status(job_id=job_id, status=status, **kwargs)
    logger.info("[JOB %s] Status '%s' persistido.", job_id, status)


def process_job(job_data: dict):
    job_id = job_data["job_id"]
    usuario_id = job_data["usuario_id"]
    url_original = job_data["url_original"]

    try:
        logger.info("[JOB %s] Iniciando processamento do job.", job_id)

        _update_job_status_com_log(
            job_id=job_id,
            status=JOB_STATUS_PROCESSANDO,
            iniciado_em=now_str()
        )

        bot = get_bot(job_id=job_id)

        try:
            link_afiliado = bot.gerar_link(url_original)
        except LoginNecessarioError:
            raise
        except FluxoGeracaoLinkError as primeira_falha:
            if not primeira_falha.retryable:
                raise

            logger.exception(
                "[JOB %s] Falha retryable na primeira tentativa (%s). Reiniciando bot para uma segunda tentativa.",
                job_id,
                primeira_falha
            )
            bot = reiniciar_bot(job_id=job_id)
            link_afiliado = bot.gerar_link(url_original)
        except Exception:
            logger.exception(
                "[JOB %s] Falha não mapeada na geração do link; sem retry automático para não mascarar erro real.",
                job_id
            )
            raise

        _update_job_status_com_log(
            job_id=job_id,
            status=JOB_STATUS_CONCLUIDO,
            finalizado_em=now_str(),
            resultado_link=link_afiliado
        )

        logger.info("[JOB %s] Persistindo link gerado.", job_id)
        create_link_gerado(
            usuario_id=usuario_id,
            job_id=job_id,
            url_original=url_original,
            url_afiliado=link_afiliado,
            status=LINK_STATUS_AGUARDANDO_VERIFICACAO,
            percentual_cashback=CASHBACK_PERCENTUAL_PADRAO,
            criado_em=now_str(),
            atualizado_em=now_str()
        )
        logger.info("[JOB %s] Link gerado persistido com sucesso.", job_id)

        logger.info("[JOB %s] Processamento finalizado com sucesso.", job_id)

    except LoginNecessarioError:
        mensagem = (
            "Login manual necessário no portal de afiliados do Mercado Livre. "
            "Use o MESMO Chrome do Selenium já aberto no DISPLAY (ex.: Xvfb/VNC), faça login no perfil "
            "persistente oficial do robô e reenvie o job."
        )
        logger.exception("[JOB %s] Job bloqueado por login manual necessário.", job_id)

        _update_job_status_com_log(
            job_id=job_id,
            status=JOB_STATUS_ERRO,
            finalizado_em=now_str(),
            mensagem_erro=mensagem
        )
    except Exception as e:
        logger.exception("[JOB %s] Erro ao processar job.", job_id)

        _update_job_status_com_log(
            job_id=job_id,
            status=JOB_STATUS_ERRO,
            finalizado_em=now_str(),
            mensagem_erro=str(e)
        )
    finally:
        logger.info("[JOB %s] Encerrando processamento do job.", job_id)


def worker_loop():
    logger.info("[WORKER] Worker iniciado e aguardando jobs.")

    while True:
        job_data = job_queue.get()
        job_id = job_data.get("job_id", "desconhecido")
        logger.info("[JOB %s] Job recebido pelo worker.", job_id)

        try:
            process_job(job_data)
        finally:
            job_queue.task_done()
            logger.info("[JOB %s] task_done sinalizado para a fila.", job_id)


worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()
