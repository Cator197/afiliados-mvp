import queue
import threading
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


job_queue = queue.Queue()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def enqueue_job(job_data: dict):
    job_queue.put(job_data)


def process_job(job_data: dict):
    job_id = job_data["job_id"]
    usuario_id = job_data["usuario_id"]
    url_original = job_data["url_original"]

    try:
        print(f"[WORKER] Iniciando job {job_id}")

        update_job_status(
            job_id=job_id,
            status=JOB_STATUS_PROCESSANDO,
            iniciado_em=now_str()
        )

        bot = get_bot()

        try:
            link_afiliado = bot.gerar_link(url_original)
        except Exception as primeira_falha:
            print(f"[WORKER] Primeira tentativa falhou no job {job_id}: {primeira_falha}")
            print("[WORKER] Tentando reiniciar o bot e repetir uma vez...")

            bot = reiniciar_bot()
            link_afiliado = bot.gerar_link(url_original)

        update_job_status(
            job_id=job_id,
            status=JOB_STATUS_CONCLUIDO,
            finalizado_em=now_str(),
            resultado_link=link_afiliado
        )

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

        print(f"[WORKER] Job {job_id} concluído com sucesso.")

    except Exception as e:
        print(f"[WORKER] Erro no job {job_id}: {e}")

        update_job_status(
            job_id=job_id,
            status=JOB_STATUS_ERRO,
            finalizado_em=now_str(),
            mensagem_erro=str(e)
        )


def worker_loop():
    print("[WORKER] Worker iniciado e aguardando jobs...")

    while True:
        job_data = job_queue.get()

        try:
            process_job(job_data)
        finally:
            job_queue.task_done()


worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()