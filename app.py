import uuid
import logging
import os
import sys
from config import HOST, PORT, DEBUG
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
import time
import re

from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session
)

from config import (
    SECRET_KEY,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_LIFETIME_MINUTES,
    ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    USER_LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    PASSWORD_RESET_RATE_LIMIT_MAX_ATTEMPTS,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_BLOCK_SECONDS,
    JOB_STATUS_NA_FILA,
    JOB_STATUS_PROCESSANDO,
    JOB_STATUS_CONCLUIDO,
    JOB_STATUS_ERRO,
    LINK_STATUS_AGUARDANDO_VERIFICACAO,
    CASHBACK_PERCENTUAL_PADRAO,
    WORKER_API_TOKEN,
    WORKER_ENABLED,
    JOB_TIMEOUT_SECONDS,
    WORKER_INACTIVE_THRESHOLD_SECONDS,
)
from repositories.usuarios_repo import (
    create_user,
    get_user_by_codigo,
    get_user_by_codigo_any_status,
    get_user_by_id,
    list_users,
    update_user_active_status,
    update_user_password,
    validate_user_login,
)
from repositories.jobs_repo import create_job, get_job_by_id, claim_next_job, update_job_status, list_jobs, reclaim_stuck_jobs, get_jobs_status_counts
from repositories.links_repo import (
    get_links_by_usuario_id,
    get_all_links,
    get_link_by_id,
    update_link_admin_fields,
    create_link_gerado,
    get_user_history_summary,
)
from repositories.admin_repo import validate_admin_login
from repositories.worker_status_repo import upsert_worker_heartbeat, get_worker_status
from repositories.cadastro_solicitacoes_repo import (
    create_cadastro_solicitacao,
    get_cadastro_solicitacao_by_id,
    list_cadastro_solicitacoes,
    update_cadastro_solicitacao_status,
    get_cadastro_solicitacao_ativa_by_email,
)
from repositories.password_reset_requests_repo import (
    RESET_REQUEST_STATUS_DONE,
    RESET_REQUEST_STATUS_IGNORED,
    RESET_REQUEST_STATUS_OPEN,
    RESET_REQUEST_STATUS_SENT,
    close_active_password_reset_requests,
    create_password_reset_request,
    get_active_password_reset_request,
    get_password_reset_request_by_id,
    list_password_reset_requests,
    update_password_reset_request,
)
from init_db import ensure_jobs_worker_columns, ensure_usuarios_password_column, ensure_worker_heartbeats_table, ensure_cadastro_solicitacoes_table, ensure_password_reset_requests_table
from init_db import ensure_jobs_platform_column, ensure_links_platform_column
from services.platform_utils import (
    PLATFORM_MERCADOLIVRE,
    PLATFORM_SHOPEE,
    detect_platform_from_url,
)

from config import DATA_DIR, LOGS_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=SESSION_LIFETIME_MINUTES)


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
ensure_usuarios_password_column()
ensure_jobs_worker_columns()
ensure_jobs_platform_column()
ensure_links_platform_column()
ensure_worker_heartbeats_table()
ensure_cadastro_solicitacoes_table()
ensure_password_reset_requests_table()


def login_required_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def get_or_create_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = uuid.uuid4().hex
        session["csrf_token"] = token
    return token


def rotate_csrf_token():
    session["csrf_token"] = uuid.uuid4().hex
    return session["csrf_token"]


def csrf_error_response():
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "erro": "CSRF token inválido ou ausente."}), 403
    return redirect(url_for("admin_login", erro="csrf"))


def validate_csrf_token():
    expected = session.get("csrf_token", "")
    provided = (
        request.form.get("csrf_token", "").strip()
        or request.headers.get("X-CSRF-Token", "").strip()
    )
    return bool(expected) and provided == expected


def csrf_protected(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not validate_csrf_token():
            return csrf_error_response()
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_or_create_csrf_token()}


def login_required_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_logged_in"):
            return f(*args, **kwargs)

        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "erro": "Sessão inválida ou expirada."}), 401

        return redirect(url_for("pagina_inicial"))
    return decorated_function


def set_user_session(usuario: dict):
    session.permanent = True
    session["user_logged_in"] = True
    session["user_id"] = usuario["id"]
    session["codigo_usuario"] = usuario["codigo_usuario"]
    session["user_nome"] = usuario["nome"]
    session["must_change_password"] = bool(usuario["must_change_password"])
    rotate_csrf_token()


def clear_user_session():
    for key in ["user_logged_in", "user_id", "codigo_usuario", "user_nome", "must_change_password"]:
        session.pop(key, None)


def user_must_change_password() -> bool:
    return bool(session.get("must_change_password"))


def password_change_required_response():
    redirect_to = url_for("pagina_alterar_senha")
    if request.path.startswith("/api/"):
        return jsonify({
            "ok": False,
            "erro": "É necessário alterar sua senha antes de continuar.",
            "redirect_to": redirect_to,
        }), 403
    return redirect(redirect_to)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


PLATFORM_LABELS = {
    PLATFORM_MERCADOLIVRE: "Mercado Livre",
    PLATFORM_SHOPEE: "Shopee",
}


def get_platform_label(plataforma: str | None) -> str:
    if not plataforma:
        return "Não informado"
    return PLATFORM_LABELS.get(plataforma, plataforma.capitalize())


def parse_datetime(dt_str: str | None):
    if not dt_str:
        return None

    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def get_request_worker_id(payload: dict | None = None) -> str:
    payload = payload or {}
    return payload.get("worker_id", "").strip() or request.headers.get("X-Worker-Id", "").strip()


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))


def admin_logado():
    return bool(session.get("admin_logged_in"))


def parse_positive_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


CADASTRO_SOLICITACAO_STATUS_VALIDOS = {"novo", "em_analise", "aprovado", "rejeitado"}
RESET_REQUEST_STATUS_VALIDOS = {
    RESET_REQUEST_STATUS_OPEN,
    RESET_REQUEST_STATUS_SENT,
    RESET_REQUEST_STATUS_DONE,
    RESET_REQUEST_STATUS_IGNORED,
}
MIN_USER_PASSWORD_LENGTH = 6
ADMIN_USER_ACTIONS = {"toggle_ativo", "reset_senha"}

CADASTRO_MIN_INTERVAL_SECONDS = 60
_last_signup_attempt_by_email = {}
_rate_limit_attempts = {}
_rate_limit_lock = Lock()


def get_client_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
    return forwarded_for or request.remote_addr or "unknown"


def get_rate_limit_key(scope: str) -> str:
    return f"{scope}:{get_client_ip()}"


def get_rate_limit_retry_after(scope: str, max_attempts: int) -> int:
    now = time.time()
    key = get_rate_limit_key(scope)

    with _rate_limit_lock:
        entry = _rate_limit_attempts.get(key)
        if not entry:
            return 0

        blocked_until = entry.get("blocked_until", 0)
        if blocked_until > now:
            return max(1, int(blocked_until - now))

        attempts = [
            attempt_at
            for attempt_at in entry.get("attempts", [])
            if now - attempt_at < RATE_LIMIT_WINDOW_SECONDS
        ]

        if attempts:
            entry["attempts"] = attempts
            entry["blocked_until"] = 0
            return 0

        _rate_limit_attempts.pop(key, None)
        return 0


def register_rate_limit_attempt(scope: str, max_attempts: int) -> None:
    now = time.time()
    key = get_rate_limit_key(scope)

    with _rate_limit_lock:
        entry = _rate_limit_attempts.setdefault(key, {"attempts": [], "blocked_until": 0})
        if entry.get("blocked_until", 0) > now:
            return

        attempts = [
            attempt_at
            for attempt_at in entry.get("attempts", [])
            if now - attempt_at < RATE_LIMIT_WINDOW_SECONDS
        ]
        attempts.append(now)

        if len(attempts) >= max_attempts:
            entry["attempts"] = []
            entry["blocked_until"] = now + RATE_LIMIT_BLOCK_SECONDS
            return

        entry["attempts"] = attempts
        entry["blocked_until"] = 0


def clear_rate_limit_attempts(scope: str) -> None:
    key = get_rate_limit_key(scope)
    with _rate_limit_lock:
        _rate_limit_attempts.pop(key, None)


def rate_limit_message() -> str:
    return "Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente."


def rate_limit_response(scope: str, max_attempts: int, html_template: str | None = None):
    retry_after = get_rate_limit_retry_after(scope, max_attempts)
    if not retry_after:
        return None

    headers = {"Retry-After": str(retry_after)}
    if html_template:
        return render_template(html_template, erro=rate_limit_message()), 429, headers

    return jsonify({"ok": False, "erro": rate_limit_message()}), 429, headers


def is_signup_rate_limited(email: str, now: datetime) -> bool:
    last_attempt = _last_signup_attempt_by_email.get(email)
    if last_attempt and (now - last_attempt).total_seconds() < CADASTRO_MIN_INTERVAL_SECONDS:
        return True

    _last_signup_attempt_by_email[email] = now
    return False


@app.route("/", methods=["GET"])
@app.route("/login", methods=["GET"])
def pagina_inicial():
    return render_template("index.html")


@app.route("/esqueci-senha", methods=["GET"])
def pagina_esqueci_senha():
    return render_template("solicitar_reset_senha.html")


@app.route("/usuario/alterar-senha", methods=["GET"])
@login_required_user
def pagina_alterar_senha():
    usuario = {
        "id": session.get("user_id"),
        "codigo_usuario": session.get("codigo_usuario"),
        "nome": session.get("user_nome"),
    }
    return render_template("alterar_senha.html", usuario=usuario)


@app.route("/usuario/<codigo_usuario>", methods=["GET"])
@login_required_user
def pagina_usuario(codigo_usuario):
    if session.get("codigo_usuario") != codigo_usuario:
        return redirect(url_for("pagina_inicial"))
    if user_must_change_password():
        return redirect(url_for("pagina_alterar_senha"))

    usuario = {
        "id": session.get("user_id"),
        "codigo_usuario": session.get("codigo_usuario"),
        "nome": session.get("user_nome"),
    }

    return render_template(
        "usuario.html",
        usuario=usuario
    )


@app.route("/historico/<codigo_usuario>", methods=["GET"])
@login_required_user
def pagina_historico(codigo_usuario):
    if session.get("codigo_usuario") != codigo_usuario:
        return redirect(url_for("pagina_inicial"))
    if user_must_change_password():
        return redirect(url_for("pagina_alterar_senha"))

    usuario = {
        "id": session.get("user_id"),
        "codigo_usuario": session.get("codigo_usuario"),
        "nome": session.get("user_nome"),
    }

    return render_template(
        "historico.html",
        usuario=usuario
    )


@app.route("/logout", methods=["GET"])
def user_logout():
    clear_user_session()
    return redirect(url_for("pagina_inicial"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        erro = request.args.get("erro", "").strip()
        erro_msg = "Sessão inválida. Atualize a página e tente novamente." if erro == "csrf" else None
        return render_template("admin_login.html", erro=erro_msg)

    blocked_response = rate_limit_response(
        "admin_login",
        ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        html_template="admin_login.html",
    )
    if blocked_response:
        return blocked_response

    if not validate_csrf_token():
        register_rate_limit_attempt("admin_login", ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
        return csrf_error_response()

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    admin = validate_admin_login(username, password)

    if not admin:
        register_rate_limit_attempt("admin_login", ADMIN_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
        return render_template(
            "admin_login.html",
            erro="Usuário ou senha inválidos."
        )

    clear_rate_limit_attempts("admin_login")
    session["admin_logged_in"] = True
    session["admin_username"] = admin["username"]
    session.permanent = True
    rotate_csrf_token()

    return redirect(url_for("admin_links"))


@app.route("/admin/logout", methods=["GET"])
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/links", methods=["GET"])
@login_required_admin
def admin_links():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    status = request.args.get("status", "").strip() or None
    codigo_usuario = request.args.get("codigo_usuario", "").strip() or None
    plataforma = request.args.get("plataforma", "").strip() or None
    page = parse_positive_int(request.args.get("page"), 1)
    limit = parse_positive_int(request.args.get("limit"), 20)

    links, total = get_all_links(
        status=status,
        codigo_usuario=codigo_usuario,
        plataforma=plataforma,
        page=page,
        limit=limit,
    )
    total_pages = max((total + limit - 1) // limit, 1)
    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "admin_links.html",
        admin_username=session.get("admin_username"),
        links=links,
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        platform_labels=PLATFORM_LABELS,
        filtros={
            "status": status or "",
            "codigo_usuario": codigo_usuario or "",
            "plataforma": plataforma or "",
        }
    )


@app.route("/admin/links/<int:link_id>/atualizar", methods=["POST"])
@login_required_admin
@csrf_protected
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


@app.route("/admin/solicitacoes", methods=["GET"])
@login_required_admin
def admin_solicitacoes():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    status = request.args.get("status", "").strip()
    status_filtro = status if status in CADASTRO_SOLICITACAO_STATUS_VALIDOS else None
    email = request.args.get("email", "").strip() or None
    codigo_indicacao = request.args.get("codigo_indicacao", "").strip() or None
    page = parse_positive_int(request.args.get("page"), 1)
    limit = parse_positive_int(request.args.get("limit"), 20)

    solicitacoes, total = list_cadastro_solicitacoes(
        status=status_filtro,
        email=email,
        codigo_indicacao=codigo_indicacao,
        page=page,
        limit=limit,
    )
    total_pages = max((total + limit - 1) // limit, 1)
    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "admin_solicitacoes.html",
        admin_username=session.get("admin_username"),
        solicitacoes=solicitacoes,
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        filtros={
            "status": status_filtro or "",
            "email": email or "",
            "codigo_indicacao": codigo_indicacao or "",
        },
    )


@app.route("/admin/solicitacoes/<int:solicitacao_id>/atualizar", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_atualizar_solicitacao(solicitacao_id):
    if not admin_logado():
        return redirect(url_for("admin_login"))

    solicitacao = get_cadastro_solicitacao_by_id(solicitacao_id)
    if not solicitacao:
        return redirect(url_for("admin_solicitacoes", erro="solicitacao_nao_encontrada"))

    status = request.form.get("status", "").strip()
    observacoes_admin = request.form.get("observacoes_admin", "")

    if status not in CADASTRO_SOLICITACAO_STATUS_VALIDOS:
        return redirect(url_for("admin_solicitacoes", erro="status_invalido"))

    update_cadastro_solicitacao_status(
        solicitacao_id=solicitacao_id,
        status=status,
        observacoes_admin=observacoes_admin,
        atualizado_em=now_str(),
    )

    return redirect(url_for("admin_solicitacoes", sucesso="1"))


@app.route("/admin/reset-senhas", methods=["GET"])
@login_required_admin
def admin_reset_senhas():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    status = request.args.get("status", "").strip()
    status_filtro = status if status in RESET_REQUEST_STATUS_VALIDOS else None
    codigo_usuario = request.args.get("codigo_usuario", "").strip() or None
    page = parse_positive_int(request.args.get("page"), 1)
    limit = parse_positive_int(request.args.get("limit"), 20)

    solicitacoes, total = list_password_reset_requests(
        status=status_filtro,
        codigo_usuario=codigo_usuario,
        page=page,
        limit=limit,
    )
    total_pages = max((total + limit - 1) // limit, 1)
    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "admin_reset_senhas.html",
        admin_username=session.get("admin_username"),
        solicitacoes=solicitacoes,
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        filtros={
            "status": status_filtro or "",
            "codigo_usuario": codigo_usuario or "",
        },
        reset_status_open=RESET_REQUEST_STATUS_OPEN,
        reset_status_sent=RESET_REQUEST_STATUS_SENT,
        reset_status_done=RESET_REQUEST_STATUS_DONE,
        reset_status_ignored=RESET_REQUEST_STATUS_IGNORED,
        erro=request.args.get("erro", "").strip() or None,
        sucesso=request.args.get("sucesso", "").strip() or None,
    )


@app.route("/admin/reset-senhas/<int:request_id>/atualizar", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_atualizar_reset_senha(request_id):
    if not admin_logado():
        return redirect(url_for("admin_login"))

    reset_request = get_password_reset_request_by_id(request_id)
    if not reset_request:
        return redirect(url_for("admin_reset_senhas", erro="Solicitação não encontrada."))

    status = request.form.get("status", "").strip()
    observacoes_admin = request.form.get("observacoes_admin", "").strip() or None
    nova_senha = request.form.get("nova_senha", "")

    if status not in RESET_REQUEST_STATUS_VALIDOS:
        return redirect(url_for("admin_reset_senhas", erro="Status inválido."))

    usuario = get_user_by_codigo_any_status(reset_request["codigo_usuario"])
    status_final = status

    if nova_senha:
        if len(nova_senha) < MIN_USER_PASSWORD_LENGTH:
            return redirect(url_for("admin_reset_senhas", erro=f"A nova senha deve ter no mínimo {MIN_USER_PASSWORD_LENGTH} caracteres."))
        if not usuario:
            return redirect(url_for("admin_reset_senhas", erro="Usuário da solicitação não encontrado."))
        update_user_password(user_id=usuario["id"], password=nova_senha, must_change_password=1)
        if status == RESET_REQUEST_STATUS_OPEN:
            status_final = RESET_REQUEST_STATUS_SENT

    update_password_reset_request(
        request_id=request_id,
        status=status_final,
        observacoes_admin=observacoes_admin,
        atualizado_em=now_str(),
    )

    return redirect(url_for("admin_reset_senhas", sucesso="Solicitação de reset atualizada."))


@app.route("/admin/usuarios/criar", methods=["GET", "POST"])
@login_required_admin
def admin_criar_usuario():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    solicitacao_id_raw = request.values.get("solicitacao_id", "").strip()
    solicitacao = None
    if solicitacao_id_raw.isdigit():
        solicitacao = get_cadastro_solicitacao_by_id(int(solicitacao_id_raw))

    if request.method == "GET":
        nome_prefill = request.args.get("nome", "").strip()
        if solicitacao and not nome_prefill:
            nome_prefill = (solicitacao["nome_completo"] or "").strip()

        return render_template(
            "admin_criar_usuario.html",
            admin_username=session.get("admin_username"),
            solicitacao=solicitacao,
            valores={
                "codigo_usuario": request.args.get("codigo_usuario", "").strip(),
                "nome": nome_prefill,
                "senha": "",
                "aprovar_solicitacao": request.args.get("aprovar_solicitacao", "").strip() == "1",
            },
            erro=None,
            sucesso=None,
        )

    if not validate_csrf_token():
        return csrf_error_response()

    codigo_usuario = request.form.get("codigo_usuario", "").strip().upper()
    nome = request.form.get("nome", "").strip()
    senha = request.form.get("senha", "")
    aprovar_solicitacao = request.form.get("aprovar_solicitacao") == "on"

    erro = None

    if not nome:
        erro = "Nome é obrigatório."
    elif not codigo_usuario:
        erro = "Código do usuário é obrigatório."
    elif get_user_by_codigo_any_status(codigo_usuario):
        erro = "Código do usuário já existe."
    elif len(senha) < MIN_USER_PASSWORD_LENGTH:
        erro = f"A senha deve ter no mínimo {MIN_USER_PASSWORD_LENGTH} caracteres."

    if erro:
        return render_template(
            "admin_criar_usuario.html",
            admin_username=session.get("admin_username"),
            solicitacao=solicitacao,
            valores={
                "codigo_usuario": codigo_usuario,
                "nome": nome,
                "senha": "",
                "aprovar_solicitacao": aprovar_solicitacao,
            },
            erro=erro,
            sucesso=None,
        ), 400

    create_user(
        codigo_usuario=codigo_usuario,
        nome=nome,
        password=senha,
        ativo=1,
        criado_em=now_str(),
        must_change_password=1,
    )

    if solicitacao and aprovar_solicitacao:
        update_cadastro_solicitacao_status(
            solicitacao_id=solicitacao["id"],
            status="aprovado",
            atualizado_em=now_str(),
        )

    return render_template(
        "admin_criar_usuario.html",
        admin_username=session.get("admin_username"),
        solicitacao=solicitacao,
        valores={
            "codigo_usuario": "",
            "nome": "",
            "senha": "",
            "aprovar_solicitacao": False,
        },
        erro=None,
        sucesso="Usuário criado com sucesso. No primeiro login ele precisará definir uma nova senha.",
    )


@app.route("/admin/usuarios", methods=["GET"])
@login_required_admin
def admin_usuarios():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    return render_template(
        "admin_usuarios.html",
        admin_username=session.get("admin_username"),
        usuarios=list_users(),
        erro=request.args.get("erro", "").strip() or None,
        sucesso=request.args.get("sucesso", "").strip() or None,
    )


@app.route("/admin/usuarios/<int:user_id>/atualizar", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_atualizar_usuario(user_id):
    if not admin_logado():
        return redirect(url_for("admin_login"))

    usuario = get_user_by_id(user_id)
    if not usuario:
        return redirect(url_for("admin_usuarios", erro="Usuário não encontrado."))

    acao = request.form.get("acao", "").strip()
    if acao not in ADMIN_USER_ACTIONS:
        return redirect(url_for("admin_usuarios", erro="Ação inválida."))

    if acao == "toggle_ativo":
        novo_status = 0 if usuario["ativo"] else 1
        update_user_active_status(user_id=user_id, ativo=novo_status)

        status_legivel = "ativado" if novo_status else "desativado"
        return redirect(
            url_for("admin_usuarios", sucesso=f"Usuário {usuario['codigo_usuario']} {status_legivel}.")
        )

    nova_senha = request.form.get("nova_senha", "")
    if len(nova_senha) < MIN_USER_PASSWORD_LENGTH:
        return redirect(
            url_for(
                "admin_usuarios",
                erro=f"A nova senha deve ter no mínimo {MIN_USER_PASSWORD_LENGTH} caracteres.",
            )
        )

    update_user_password(user_id=user_id, password=nova_senha, must_change_password=1)
    return redirect(
        url_for("admin_usuarios", sucesso=f"Senha do usuário {usuario['codigo_usuario']} atualizada. Ele deverá alterá-la no próximo acesso.")
    )


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


@app.route("/api/login", methods=["POST"])
def login_usuario():
    blocked_response = rate_limit_response("api_login", USER_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
    if blocked_response:
        return blocked_response

    data = request.get_json(silent=True) or {}
    codigo_usuario = data.get("codigo_usuario", "").strip().upper()
    senha = data.get("senha", "")

    if not codigo_usuario:
        register_rate_limit_attempt("api_login", USER_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
        return jsonify({"ok": False, "erro": "Código do usuário não informado."}), 400

    if not senha:
        register_rate_limit_attempt("api_login", USER_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
        return jsonify({"ok": False, "erro": "Senha não informada."}), 400

    resultado = validate_user_login(codigo_usuario, senha)

    if not resultado["ok"]:
        register_rate_limit_attempt("api_login", USER_LOGIN_RATE_LIMIT_MAX_ATTEMPTS)
        return jsonify({"ok": False, "erro": resultado["erro"]}), resultado["status_code"]

    usuario = resultado["usuario"]
    clear_rate_limit_attempts("api_login")
    set_user_session(usuario)
    must_change_password = bool(usuario["must_change_password"])
    redirect_to = url_for("pagina_alterar_senha") if must_change_password else url_for("pagina_usuario", codigo_usuario=usuario["codigo_usuario"])

    return jsonify({
        "ok": True,
        "usuario": {
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"],
        },
        "must_change_password": must_change_password,
        "redirect_to": redirect_to,
    })


@app.route("/api/validar-usuario", methods=["POST"])
def validar_usuario():
    return jsonify({
        "ok": False,
        "erro": "Fluxo legado desativado. Utilize /api/login com código e senha."
    }), 410


@app.route("/api/alterar-senha", methods=["POST"])
@login_required_user
@csrf_protected
def alterar_senha_usuario():
    data = request.get_json(silent=True) or {}
    senha_atual = data.get("senha_atual", "")
    nova_senha = data.get("nova_senha", "")
    confirmar_senha = data.get("confirmar_senha", "")

    if not senha_atual:
        return jsonify({"ok": False, "erro": "Informe a senha atual."}), 400

    if len(nova_senha) < MIN_USER_PASSWORD_LENGTH:
        return jsonify({"ok": False, "erro": f"A nova senha deve ter no mínimo {MIN_USER_PASSWORD_LENGTH} caracteres."}), 400

    if nova_senha != confirmar_senha:
        return jsonify({"ok": False, "erro": "A confirmação da nova senha não confere."}), 400

    codigo_usuario = session.get("codigo_usuario", "")
    validacao = validate_user_login(codigo_usuario, senha_atual)
    if not validacao["ok"]:
        return jsonify({"ok": False, "erro": "Senha atual inválida."}), 401

    usuario_id = session.get("user_id")
    usuario = get_user_by_id(usuario_id) if usuario_id else None
    if not usuario:
        return jsonify({"ok": False, "erro": "Usuário não encontrado."}), 404

    update_user_password(user_id=usuario["id"], password=nova_senha, must_change_password=0)
    session["must_change_password"] = False
    rotate_csrf_token()
    close_active_password_reset_requests(codigo_usuario=usuario["codigo_usuario"], atualizado_em=now_str())

    return jsonify({
        "ok": True,
        "message": "Senha alterada com sucesso.",
        "redirect_to": url_for("pagina_usuario", codigo_usuario=usuario["codigo_usuario"]),
        "csrf_token": session.get("csrf_token"),
    })


@app.route("/solicitar-cadastro", methods=["GET"])
def pagina_solicitar_cadastro():
    return render_template("solicitar_cadastro.html")


@app.route("/api/solicitar-cadastro", methods=["POST"])
def solicitar_cadastro_publico():
    data = request.get_json(silent=True) or {}

    nome_completo = data.get("nome_completo", "").strip()
    email = data.get("email", "").strip().lower()
    codigo_indicacao = data.get("codigo_indicacao", "").strip() or None

    if not nome_completo:
        return jsonify({"ok": False, "erro": "Nome completo é obrigatório."}), 400

    if not email:
        return jsonify({"ok": False, "erro": "Email é obrigatório."}), 400

    if not is_valid_email(email):
        return jsonify({"ok": False, "erro": "Email inválido."}), 400

    solicitacao_existente = get_cadastro_solicitacao_ativa_by_email(email)
    if solicitacao_existente:
        return jsonify({"ok": False, "erro": "Já existe solicitação em análise"}), 409

    if is_signup_rate_limited(email=email, now=datetime.now()):
        return jsonify({"ok": False, "erro": "Tente novamente mais tarde"}), 429

    try:
        solicitacao_id = create_cadastro_solicitacao(
            nome_completo=nome_completo,
            email=email,
            codigo_indicacao=codigo_indicacao,
            whatsapp=None,
            status="novo",
            criado_em=now_str(),
            atualizado_em=now_str(),
        )
    except Exception:
        app.logger.exception("Falha ao criar solicitação de cadastro.")
        return jsonify({"ok": False, "erro": "Não foi possível registrar sua solicitação agora. Tente novamente."}), 500

    return jsonify({
        "ok": True,
        "message": "Solicitação enviada com sucesso. Em breve faremos a análise manual.",
        "solicitacao_id": solicitacao_id,
    }), 201


@app.route("/api/esqueci-senha", methods=["POST"])
def solicitar_reset_senha_publico():
    blocked_response = rate_limit_response("api_esqueci_senha", PASSWORD_RESET_RATE_LIMIT_MAX_ATTEMPTS)
    if blocked_response:
        return blocked_response

    register_rate_limit_attempt("api_esqueci_senha", PASSWORD_RESET_RATE_LIMIT_MAX_ATTEMPTS)

    data = request.get_json(silent=True) or {}
    codigo_usuario = data.get("codigo_usuario", "").strip().upper()

    if not codigo_usuario:
        return jsonify({"ok": False, "erro": "Informe seu código de usuário."}), 400

    usuario = get_user_by_codigo_any_status(codigo_usuario)
    if not usuario or not usuario["ativo"]:
        return jsonify({"ok": False, "erro": "Usuário não encontrado ou inativo."}), 404

    solicitacao_existente = get_active_password_reset_request(codigo_usuario)
    if solicitacao_existente:
        return jsonify({"ok": False, "erro": "Já existe uma solicitação de redefinição em andamento para esse usuário."}), 409

    request_id = create_password_reset_request(
        codigo_usuario=codigo_usuario,
        criado_em=now_str(),
        atualizado_em=now_str(),
    )

    return jsonify({
        "ok": True,
        "message": "Solicitação enviada. O administrador irá gerar uma nova senha temporária para você.",
        "request_id": request_id,
    }), 201


@app.route("/api/solicitar-link", methods=["POST"])
@login_required_user
@csrf_protected
def solicitar_link():
    if user_must_change_password():
        return password_change_required_response()

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()

    if not url:
        return jsonify({
            "ok": False,
            "erro": "URL não informada."
        }), 400

    plataforma = detect_platform_from_url(url)
    if not plataforma:
        return jsonify({
            "ok": False,
            "erro": "A URL informada não pertence a uma plataforma suportada."
        }), 400

    usuario_id = session.get("user_id")
    usuario = get_user_by_id(usuario_id) if usuario_id else None
    if not usuario:
        return jsonify({
            "ok": False,
            "erro": "Usuário não encontrado."
        }), 404

    job_id = str(uuid.uuid4())
    app.logger.info(
        "[JOB %s] Recebida solicitação de geração de link | usuario=%s | url=%s",
        job_id,
        usuario["codigo_usuario"],
        url,
    )

    create_job(
        job_id=job_id,
        usuario_id=usuario["id"],
        url_original=url,
        plataforma=plataforma,
        status=JOB_STATUS_NA_FILA,
        criado_em=now_str()
    )
    app.logger.info("[JOB %s] Job persistido com status inicial '%s'.", job_id, JOB_STATUS_NA_FILA)

    app.logger.info(
        "[JOB %s] Job aguardando claim do worker remoto em /api/worker/jobs/claim.",
        job_id,
    )

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "status": JOB_STATUS_NA_FILA,
        "plataforma": plataforma,
        "plataforma_label": get_platform_label(plataforma),
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

    reclaimed = reclaim_stuck_jobs(
        claimed_em_cutoff=(datetime.now() - timedelta(seconds=JOB_TIMEOUT_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    )
    if reclaimed > 0:
        app.logger.warning(
            "[WORKER %s] Reclaim executado. %s job(s) preso(s) retornaram para '%s'.",
            worker_id,
            reclaimed,
            JOB_STATUS_NA_FILA,
        )

    job = claim_next_job(worker_id=worker_id, claimed_em=now_str())

    if not job:
        app.logger.info("[WORKER %s] Nenhum job disponível para claim no momento.", worker_id)
        return jsonify({"ok": True, "job": None})

    app.logger.info(
        "[JOB %s] Claim efetuado com sucesso pelo worker remoto '%s'.",
        job["id"],
        worker_id,
    )

    return jsonify({
        "ok": True,
        "job": {
            "id": job["id"],
            "usuario_id": job["usuario_id"],
            "url_original": job["url_original"],
            "plataforma": job["plataforma"],
            "plataforma_label": get_platform_label(job["plataforma"]),
            "status": job["status"],
            "assigned_worker_id": job["assigned_worker_id"],
            "claimed_em": job["claimed_em"],
            "criado_em": job["criado_em"],
        }
    })


@app.route("/api/worker/heartbeat", methods=["POST"])
def worker_heartbeat():
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    worker_id = get_request_worker_id(data)

    if not worker_id:
        return jsonify({"ok": False, "erro": "worker_id não informado."}), 400

    last_status = data.get("status", "").strip() or None
    last_message = data.get("message", "").strip() or None
    heartbeat_em = now_str()

    upsert_worker_heartbeat(
        worker_id=worker_id,
        last_heartbeat_em=heartbeat_em,
        last_status=last_status,
        last_message=last_message,
    )
    app.logger.info(
        "[WORKER %s] Heartbeat recebido | status=%s | message=%s",
        worker_id,
        last_status or "-",
        last_message or "-",
    )

    return jsonify({"ok": True, "worker_id": worker_id, "last_heartbeat_em": heartbeat_em})


@app.route("/api/worker/jobs/<job_id>/success", methods=["POST"])
def worker_job_success(job_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    worker_id = get_request_worker_id(data)
    url_afiliado = data.get("url_afiliado", "").strip()

    if not url_afiliado:
        return jsonify({"ok": False, "erro": "url_afiliado não informada."}), 400

    job = get_job_by_id(job_id)
    if not job:
        return jsonify({"ok": False, "erro": "Job não encontrado."}), 404

    if job["status"] != JOB_STATUS_PROCESSANDO:
        app.logger.warning(
            "[JOB %s] Success fora de contexto. status_atual=%s worker_reportado=%s",
            job_id,
            job["status"],
            worker_id or "-",
        )
        return jsonify({"ok": False, "erro": "Job fora de contexto para success."}), 409

    if worker_id and job["assigned_worker_id"] and worker_id != job["assigned_worker_id"]:
        app.logger.warning(
            "[JOB %s] Success com worker divergente. assigned=%s recebido=%s",
            job_id,
            job["assigned_worker_id"],
            worker_id,
        )
        return jsonify({"ok": False, "erro": "worker_id divergente do job claimado."}), 409

    update_job_status(
        job_id=job_id,
        status=JOB_STATUS_CONCLUIDO,
        finalizado_em=now_str(),
        resultado_link=url_afiliado,
        mensagem_erro="",
    )
    app.logger.info("[JOB %s] Success recebido do worker remoto.", job_id)

    create_link_gerado(
        usuario_id=job["usuario_id"],
        job_id=job_id,
        url_original=job["url_original"],
        plataforma=job["plataforma"] or PLATFORM_MERCADOLIVRE,
        url_afiliado=url_afiliado,
        status=LINK_STATUS_AGUARDANDO_VERIFICACAO,
        percentual_cashback=CASHBACK_PERCENTUAL_PADRAO,
        criado_em=now_str(),
        atualizado_em=now_str(),
    )
    app.logger.info("[JOB %s] Link afiliado persistido e job concluído.", job_id)

    return jsonify({"ok": True, "job_id": job_id, "status": JOB_STATUS_CONCLUIDO})


@app.route("/api/worker/jobs/<job_id>/error", methods=["POST"])
def worker_job_error(job_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    worker_id = get_request_worker_id(data)
    mensagem_erro = data.get("mensagem_erro", "").strip()

    if not mensagem_erro:
        return jsonify({"ok": False, "erro": "mensagem_erro não informada."}), 400

    job = get_job_by_id(job_id)
    if not job:
        return jsonify({"ok": False, "erro": "Job não encontrado."}), 404

    if job["status"] != JOB_STATUS_PROCESSANDO:
        app.logger.warning(
            "[JOB %s] Error fora de contexto. status_atual=%s worker_reportado=%s",
            job_id,
            job["status"],
            worker_id or "-",
        )
        return jsonify({"ok": False, "erro": "Job fora de contexto para error."}), 409

    if worker_id and job["assigned_worker_id"] and worker_id != job["assigned_worker_id"]:
        app.logger.warning(
            "[JOB %s] Error com worker divergente. assigned=%s recebido=%s",
            job_id,
            job["assigned_worker_id"],
            worker_id,
        )
        return jsonify({"ok": False, "erro": "worker_id divergente do job claimado."}), 409

    update_job_status(
        job_id=job_id,
        status=JOB_STATUS_ERRO,
        finalizado_em=now_str(),
        mensagem_erro=mensagem_erro,
    )
    app.logger.info("[JOB %s] Error recebido do worker remoto: %s", job_id, mensagem_erro)

    return jsonify({"ok": True, "job_id": job_id, "status": JOB_STATUS_ERRO})


@app.route("/api/jobs/<job_id>", methods=["GET"])
@login_required_user
def consultar_job(job_id):
    if user_must_change_password():
        return password_change_required_response()

    job = get_job_by_id(job_id)

    if not job:
        return jsonify({
            "ok": False,
            "erro": "Job não encontrado."
        }), 404

    if job["usuario_id"] != session.get("user_id"):
        return jsonify({
            "ok": False,
            "erro": "Acesso negado."
        }), 403

    return jsonify({
        "ok": True,
        "job": {
            "id": job["id"],
            "usuario_id": job["usuario_id"],
            "url_original": job["url_original"],
            "plataforma": job["plataforma"],
            "plataforma_label": get_platform_label(job["plataforma"]),
            "status": job["status"],
            "resultado_link": job["resultado_link"],
            "mensagem_erro": job["mensagem_erro"],
            "criado_em": job["criado_em"],
            "iniciado_em": job["iniciado_em"],
            "finalizado_em": job["finalizado_em"]
        }
    })


@app.route("/api/usuario/<codigo_usuario>/resumo", methods=["GET"])
@login_required_user
def resumo_links_usuario(codigo_usuario):
    if session.get("codigo_usuario") != codigo_usuario:
        return jsonify({
            "ok": False,
            "erro": "Acesso negado."
        }), 403
    if user_must_change_password():
        return password_change_required_response()

    usuario = get_user_by_codigo(codigo_usuario)

    if not usuario:
        return jsonify({
            "ok": False,
            "erro": "Usuário não encontrado."
        }), 404

    summary = get_user_history_summary(usuario["id"])

    return jsonify({
        "ok": True,
        "usuario": {
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        },
        "summary": summary
    })


@app.route("/api/usuario/<codigo_usuario>/links", methods=["GET"])
@login_required_user
def listar_links_usuario(codigo_usuario):
    if session.get("codigo_usuario") != codigo_usuario:
        return jsonify({
            "ok": False,
            "erro": "Acesso negado."
        }), 403
    if user_must_change_password():
        return password_change_required_response()

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
                "plataforma": link["plataforma"],
                "plataforma_label": get_platform_label(link["plataforma"]),
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


@app.route("/api/admin/worker-status", methods=["GET"])
def api_worker_status():
    if not admin_logado():
        return jsonify({
            "ok": False,
            "erro": "Não autorizado."
        }), 401

    worker_id_filter = request.args.get("worker_id", "").strip() or None
    worker = get_worker_status(worker_id_filter)
    status_counts = get_jobs_status_counts()

    jobs_na_fila = status_counts.get(JOB_STATUS_NA_FILA, 0)
    jobs_processando = status_counts.get(JOB_STATUS_PROCESSANDO, 0)
    jobs_erro = status_counts.get(JOB_STATUS_ERRO, 0)

    inactive = None
    inactive_for_seconds = None

    if worker:
        last_heartbeat_dt = parse_datetime(worker["last_heartbeat_em"])
        if last_heartbeat_dt:
            inactive_for_seconds = int((datetime.now() - last_heartbeat_dt).total_seconds())
            inactive = inactive_for_seconds > WORKER_INACTIVE_THRESHOLD_SECONDS
            if inactive:
                app.logger.warning(
                    "[WORKER %s] Considerado inativo. Último heartbeat há %ss (limite=%ss).",
                    worker["worker_id"],
                    inactive_for_seconds,
                    WORKER_INACTIVE_THRESHOLD_SECONDS,
                )

    return jsonify({
        "ok": True,
        "worker": {
            "worker_id": worker["worker_id"] if worker else None,
            "last_heartbeat_em": worker["last_heartbeat_em"] if worker else None,
            "last_status": worker["last_status"] if worker else None,
            "last_message": worker["last_message"] if worker else None,
            "inactive": inactive,
            "inactive_for_seconds": inactive_for_seconds,
            "inactive_threshold_seconds": WORKER_INACTIVE_THRESHOLD_SECONDS,
        },
        "jobs": {
            "na_fila": jobs_na_fila,
            "processando": jobs_processando,
            "erro": jobs_erro,
        }
    })


@app.route("/api/admin/bot-status", methods=["GET"])
def api_bot_status():
    if not admin_logado():
        return jsonify({
            "ok": False,
            "erro": "Não autorizado."
        }), 401

    jobs = list_jobs()
    jobs_na_fila = sum(1 for job in jobs if job["status"] == JOB_STATUS_NA_FILA)
    jobs_processando = sum(1 for job in jobs if job["status"] == JOB_STATUS_PROCESSANDO)

    if not WORKER_ENABLED:
        status = "erro_recuperacao"
        message = "Worker remoto desabilitado na VPS (WORKER_ENABLED=false)."
    elif jobs_processando > 0:
        status = "online"
        message = "Modo remoto ativo. Há job(s) em processamento por worker remoto."
    else:
        status = "aguardando_login_manual" if jobs_na_fila > 0 else "online"
        message = (
            f"Modo remoto ativo. Jobs aguardando worker remoto: {jobs_na_fila}."
            if jobs_na_fila > 0
            else "Modo remoto ativo. Aguardando novos jobs."
        )

    return jsonify({
        "ok": True,
        "bot": {
            "status": status,
            "message": message,
        }
    })


if __name__ == "__main__":
    host = HOST or "0.0.0.0"
    app.logger.info(f"Iniciando servidor Flask em {host}:{PORT}")
    app.run(host=host, port=PORT, debug=DEBUG)
