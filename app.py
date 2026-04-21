import uuid
import logging
import os
import sys
from config import HOST, PORT, DEBUG
from datetime import datetime
from functools import wraps

from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session
)

from config import (
    SECRET_KEY,
    DOMINIOS_PERMITIDOS,
    JOB_STATUS_NA_FILA,
    JOB_STATUS_CONCLUIDO,
    JOB_STATUS_ERRO,
    LINK_STATUS_AGUARDANDO_VERIFICACAO,
    CASHBACK_PERCENTUAL_PADRAO,
    WORKER_API_TOKEN,
    WORKER_ENABLED,
)
from repositories.usuarios_repo import get_user_by_codigo
from repositories.jobs_repo import create_job, get_job_by_id, claim_next_job, update_job_status
from repositories.links_repo import (
    get_links_by_usuario_id,
    get_all_links,
    get_link_by_id,
    update_link_admin_fields,
    create_link_gerado,
)
from repositories.admin_repo import validate_admin_login
from bot_manager import get_bot_status
from init_db import ensure_jobs_worker_columns

from config import DATA_DIR, LOGS_DIR

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

app = Flask(__name__)
app.secret_key = SECRET_KEY


def configure_logging():
    gunicorn_logger = logging.getLogger("gunicorn.error")
    root_logger = logging.getLogger()

    if gunicorn_logger.handlers:
        root_logger.handlers = gunicorn_logger.handlers
        root_logger.setLevel(gunicorn_logger.level or logging.INFO)
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level or logging.INFO)
        return

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(LOGS_DIR, "app.log")),
        ],
    )
    app.logger.setLevel(logging.INFO)


configure_logging()
ensure_jobs_worker_columns()

def login_required_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_valid_mercadolivre_url(url: str) -> bool:
    if not url.startswith("http"):
        return False

    url_lower = url.lower()
    return any(dominio in url_lower for dominio in DOMINIOS_PERMITIDOS)


def admin_logado():
    return bool(session.get("admin_logged_in"))


@app.route("/", methods=["GET"])
def pagina_inicial():
    return render_template("index.html")


@app.route("/usuario/<codigo_usuario>", methods=["GET"])
def pagina_usuario(codigo_usuario):
    usuario = get_user_by_codigo(codigo_usuario)

    if not usuario:
        return redirect(url_for("pagina_inicial"))

    return render_template(
        "usuario.html",
        usuario={
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        }
    )


@app.route("/historico/<codigo_usuario>", methods=["GET"])
def pagina_historico(codigo_usuario):
    usuario = get_user_by_codigo(codigo_usuario)

    if not usuario:
        return redirect(url_for("pagina_inicial"))

    return render_template(
        "historico.html",
        usuario={
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        }
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    admin = validate_admin_login(username, password)

    if not admin:
        return render_template(
            "admin_login.html",
            erro="Usuário ou senha inválidos."
        )

    session["admin_logged_in"] = True
    session["admin_username"] = admin["username"]

    return redirect(url_for("admin_links"))


@app.route("/admin/logout", methods=["GET"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/links", methods=["GET"])
@login_required_admin
def admin_links():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    status = request.args.get("status", "").strip() or None
    codigo_usuario = request.args.get("codigo_usuario", "").strip() or None

    links = get_all_links(status=status, codigo_usuario=codigo_usuario)

    return render_template(
        "admin_links.html",
        admin_username=session.get("admin_username"),
        links=links,
        filtros={
            "status": status or "",
            "codigo_usuario": codigo_usuario or ""
        }
    )


@app.route("/admin/links/<int:link_id>/atualizar", methods=["POST"])
@login_required_admin
def admin_atualizar_link(link_id):
    if not admin_logado():
        return redirect(url_for("admin_login"))

    link = get_link_by_id(link_id)
    if not link:
        return redirect(url_for("admin_links"))

    status = request.form.get("status", "").strip() or None
    valor_comissao_raw = request.form.get("valor_comissao", "").strip()
    percentual_cashback_raw = request.form.get("percentual_cashback", "").strip()
    observacoes_admin = request.form.get("observacoes_admin", "").strip() or None

    valor_comissao = None
    percentual_cashback = None
    valor_cashback = None

    if valor_comissao_raw:
        try:
            valor_comissao = float(valor_comissao_raw.replace(",", "."))
        except ValueError:
            valor_comissao = None

    if percentual_cashback_raw:
        try:
            percentual_cashback = float(percentual_cashback_raw.replace(",", "."))
        except ValueError:
            percentual_cashback = None

    percentual_base = percentual_cashback if percentual_cashback is not None else link["percentual_cashback"]

    if valor_comissao is not None and percentual_base is not None:
        valor_cashback = round(valor_comissao * percentual_base / 100, 2)

    update_link_admin_fields(
        link_id=link_id,
        status=status,
        valor_comissao=valor_comissao,
        percentual_cashback=percentual_cashback,
        valor_cashback=valor_cashback,
        observacoes_admin=observacoes_admin,
        atualizado_em=now_str()
    )

    return redirect(url_for("admin_links", sucesso="1"))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "message": "API online"
    })



def worker_token_is_valid(token: str) -> bool:
    if not WORKER_ENABLED:
        return False

    configured_token = (WORKER_API_TOKEN or "").strip()
    return bool(configured_token) and token == configured_token


def validate_worker_request():
    worker_token = request.headers.get("X-Worker-Token", "").strip()

    if not WORKER_ENABLED:
        return jsonify({"ok": False, "erro": "Worker desabilitado."}), 503

    if not worker_token_is_valid(worker_token):
        return jsonify({"ok": False, "erro": "Não autorizado."}), 401

    return None

@app.route("/api/validar-usuario", methods=["POST"])
def validar_usuario():
    data = request.get_json(silent=True) or {}
    codigo_usuario = data.get("codigo_usuario", "").strip()

    if not codigo_usuario:
        return jsonify({
            "ok": False,
            "erro": "Código do usuário não informado."
        }), 400

    usuario = get_user_by_codigo(codigo_usuario)

    if not usuario:
        logging.warning(f"Tentativa de acesso com ID inexistente: {codigo_usuario}")
        return jsonify({
            "ok": False,
            "erro": "Usuário não encontrado."
        }), 404

    return jsonify({
        "ok": True,
        "usuario": {
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        }
    })


@app.route("/api/solicitar-link", methods=["POST"])
def solicitar_link():
    data = request.get_json(silent=True) or {}

    codigo_usuario = data.get("codigo_usuario", "").strip()
    url = data.get("url", "").strip()

    if not codigo_usuario:
        return jsonify({
            "ok": False,
            "erro": "Código do usuário não informado."
        }), 400

    if not url:
        return jsonify({
            "ok": False,
            "erro": "URL não informada."
        }), 400

    if not is_valid_mercadolivre_url(url):
        return jsonify({
            "ok": False,
            "erro": "A URL informada não é do Mercado Livre."
        }), 400

    usuario = get_user_by_codigo(codigo_usuario)
    if not usuario:
        return jsonify({
            "ok": False,
            "erro": "Usuário não encontrado."
        }), 404

    job_id = str(uuid.uuid4())
    app.logger.info(
        "[JOB %s] Recebida solicitação de geração de link | usuario=%s | url=%s",
        job_id,
        codigo_usuario,
        url,
    )

    create_job(
        job_id=job_id,
        usuario_id=usuario["id"],
        url_original=url,
        status=JOB_STATUS_NA_FILA,
        criado_em=now_str()
    )
    app.logger.info("[JOB %s] Job persistido com status inicial '%s'.", job_id, JOB_STATUS_NA_FILA)

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "status": JOB_STATUS_NA_FILA
    })


@app.route("/api/worker/jobs/claim", methods=["POST"])
def worker_claim_job():
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id", "").strip() or request.headers.get("X-Worker-Id", "").strip()

    if not worker_id:
        return jsonify({"ok": False, "erro": "worker_id não informado."}), 400

    job = claim_next_job(worker_id=worker_id, claimed_em=now_str())

    if not job:
        return jsonify({"ok": True, "job": None})

    return jsonify({
        "ok": True,
        "job": {
            "id": job["id"],
            "usuario_id": job["usuario_id"],
            "url_original": job["url_original"],
            "status": job["status"],
            "assigned_worker_id": job["assigned_worker_id"],
            "claimed_em": job["claimed_em"],
            "criado_em": job["criado_em"],
        }
    })


@app.route("/api/worker/jobs/<job_id>/success", methods=["POST"])
def worker_job_success(job_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    url_afiliado = data.get("url_afiliado", "").strip()

    if not url_afiliado:
        return jsonify({"ok": False, "erro": "url_afiliado não informada."}), 400

    job = get_job_by_id(job_id)
    if not job:
        return jsonify({"ok": False, "erro": "Job não encontrado."}), 404

    update_job_status(
        job_id=job_id,
        status=JOB_STATUS_CONCLUIDO,
        finalizado_em=now_str(),
        resultado_link=url_afiliado,
        mensagem_erro="",
    )

    create_link_gerado(
        usuario_id=job["usuario_id"],
        job_id=job_id,
        url_original=job["url_original"],
        url_afiliado=url_afiliado,
        status=LINK_STATUS_AGUARDANDO_VERIFICACAO,
        percentual_cashback=CASHBACK_PERCENTUAL_PADRAO,
        criado_em=now_str(),
        atualizado_em=now_str(),
    )

    return jsonify({"ok": True, "job_id": job_id, "status": JOB_STATUS_CONCLUIDO})


@app.route("/api/worker/jobs/<job_id>/error", methods=["POST"])
def worker_job_error(job_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    mensagem_erro = data.get("mensagem_erro", "").strip()

    if not mensagem_erro:
        return jsonify({"ok": False, "erro": "mensagem_erro não informada."}), 400

    job = get_job_by_id(job_id)
    if not job:
        return jsonify({"ok": False, "erro": "Job não encontrado."}), 404

    update_job_status(
        job_id=job_id,
        status=JOB_STATUS_ERRO,
        finalizado_em=now_str(),
        mensagem_erro=mensagem_erro,
    )

    return jsonify({"ok": True, "job_id": job_id, "status": JOB_STATUS_ERRO})


@app.route("/api/jobs/<job_id>", methods=["GET"])
def consultar_job(job_id):
    job = get_job_by_id(job_id)

    if not job:
        return jsonify({
            "ok": False,
            "erro": "Job não encontrado."
        }), 404

    return jsonify({
        "ok": True,
        "job": {
            "id": job["id"],
            "usuario_id": job["usuario_id"],
            "url_original": job["url_original"],
            "status": job["status"],
            "resultado_link": job["resultado_link"],
            "mensagem_erro": job["mensagem_erro"],
            "criado_em": job["criado_em"],
            "iniciado_em": job["iniciado_em"],
            "finalizado_em": job["finalizado_em"]
        }
    })


@app.route("/api/usuario/<codigo_usuario>/links", methods=["GET"])
def listar_links_usuario(codigo_usuario):
    usuario = get_user_by_codigo(codigo_usuario)

    if not usuario:
        return jsonify({
            "ok": False,
            "erro": "Usuário não encontrado."
        }), 404

    links = get_links_by_usuario_id(usuario["id"])

    return jsonify({
        "ok": True,
        "usuario": {
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        },
        "links": [
            {
                "id": link["id"],
                "job_id": link["job_id"],
                "url_original": link["url_original"],
                "url_afiliado": link["url_afiliado"],
                "status": link["status"],
                "percentual_cashback": link["percentual_cashback"],
                "valor_comissao": link["valor_comissao"],
                "valor_cashback": link["valor_cashback"],
                "observacoes_admin": link["observacoes_admin"],
                "criado_em": link["criado_em"],
                "atualizado_em": link["atualizado_em"]
            }
            for link in links
        ]
    })

@app.route("/api/admin/bot-status", methods=["GET"])
def api_bot_status():
    if not admin_logado():
        return jsonify({
            "ok": False,
            "erro": "Não autorizado."
        }), 401

    return jsonify({
        "ok": True,
        "bot": get_bot_status()
    })

if __name__ == "__main__":
    host = HOST or "0.0.0.0"
    app.logger.info(f"Iniciando servidor Flask em {host}:{PORT}")
    app.run(host=host, port=PORT, debug=DEBUG)
