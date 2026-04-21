import uuid
from datetime import datetime

from config import JOB_STATUS_NA_FILA
from repositories.usuarios_repo import get_user_by_codigo
from repositories.jobs_repo import create_job, get_job_by_id
from queue_manager import enqueue_job


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


codigo_usuario = "CAIO001"
url_original = input("Cole uma URL do Mercado Livre: ").strip()

usuario = get_user_by_codigo(codigo_usuario)
if not usuario:
    raise Exception("Usuário não encontrado.")

job_id = str(uuid.uuid4())

create_job(
    job_id=job_id,
    usuario_id=usuario["id"],
    url_original=url_original,
    plataforma="mercadolivre",
    status=JOB_STATUS_NA_FILA,
    criado_em=now_str()
)

enqueue_job({
    "job_id": job_id,
    "usuario_id": usuario["id"],
    "url_original": url_original,
    "plataforma": "mercadolivre",
})

print(f"Job enviado para fila: {job_id}")
input("Pressione ENTER depois que o worker terminar... ")

job = get_job_by_id(job_id)
print(dict(job))
