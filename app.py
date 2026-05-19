import uuid
import logging
import os
import sys
import hmac
import hashlib
import secrets
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
    LINK_STATUS_COMPRA_CONFIRMADA,
    LINK_STATUS_COMPRA_NAO_CONFIRMADA,
    LINK_STATUS_CASHBACK_PAGO,
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
    get_user_by_email,
    get_user_by_codigo_or_email,
    list_users,
    list_users_admin,
    update_user_active_status,
    update_user_email,
    update_user_password,
    validate_user_login,
)
from repositories.jobs_repo import create_job, get_job_by_id, claim_next_job, update_job_status, list_jobs, reclaim_stuck_jobs, get_jobs_status_counts
from repositories.links_repo import (
    get_links_by_usuario_id,
    get_all_links,
    get_link_by_id,
    claim_next_metadata_job,
    reenfileirar_metadados,
    recalcular_valores,
    update_link_admin_fields,
    update_product_metadata,
    create_link_gerado,
    get_user_history_summary,
)
from repositories.admin_repo import validate_admin_login
from repositories.worker_status_repo import upsert_worker_heartbeat, get_worker_status
from repositories.worker_diagnostics_repo import (
    create_diagnostic,
    update_diagnostic,
    get_last_diagnostics,
    claim_pending_diagnostic,
)
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
    create_password_reset_token,
    get_valid_reset_token,
    mark_reset_token_used,
    invalidate_active_tokens_for_user,
)
from repositories.admin_dashboard_repo import (
    count_links_by_status,
    get_recent_links_by_status,
    count_users_without_email,
    get_users_without_email,
    count_pending_signup_requests,
    count_pending_password_reset_requests,
    get_last_worker_diagnostic,
    get_last_worker_heartbeat,
)
from repositories.password_reset_attempts_repo import (
    count_recent_attempts_by_identifier,
    count_recent_attempts_by_ip,
    create_password_reset_attempt,
)
from init_db import ensure_jobs_worker_columns, ensure_usuarios_password_column, ensure_usuarios_email_column, ensure_worker_heartbeats_table, ensure_cadastro_solicitacoes_table, ensure_password_reset_requests_table, ensure_password_reset_tokens_table, ensure_password_reset_attempts_table, ensure_worker_diagnostics_table
from init_db import ensure_jobs_platform_column, ensure_links_platform_column, ensure_links_metadata_columns
from services.extension_service import build_extension_status_response, build_product_preview
from services.platform_utils import (
    PLATFORM_MERCADOLIVRE,
    PLATFORM_SHOPEE,
    PLATFORM_MERCADOLIVRE,
    detect_platform_from_url,
)

from config import (
    DATA_DIR,
    LOGS_DIR,
    EMAIL_ENABLED,
    SMTP_FROM_EMAIL,
    ADMIN_NOTIFICATION_EMAIL,
)
from services.status_labels import (
    get_status_label,
    get_status_description,
    get_status_badge_class,
    get_status_next_action,
)
from services.email_service import (
    send_test_email,
    notify_admin_new_signup_request,
    notify_admin_password_reset_request,
    notify_admin_new_link_pending,
    notify_user_signup_approved,
    notify_user_signup_rejected,
    notify_user_purchase_confirmed,
    notify_user_purchase_not_confirmed,
    notify_user_cashback_paid,
    send_password_reset_email,
)

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
ensure_usuarios_email_column()
ensure_jobs_worker_columns()
ensure_jobs_platform_column()
ensure_links_platform_column()
ensure_links_metadata_columns()
ensure_worker_heartbeats_table()
ensure_worker_diagnostics_table()
ensure_cadastro_solicitacoes_table()
ensure_password_reset_requests_table()
ensure_password_reset_tokens_table()
ensure_password_reset_attempts_table()


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

    header_candidates = (
        "X-CSRF-Token",
        "X-CSRFToken",
        "X-Csrf-Token",
        "X-CsrfToken",
    )
    header_token = ""
    for header_name in header_candidates:
        header_token = request.headers.get(header_name, "").strip()
        if header_token:
            break

    provided = request.form.get("csrf_token", "").strip() or header_token
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
    PLATFORM_SHOPEE: "Shopee (legado)",
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


def parse_decimal_input(value_raw: str, field_label: str):
    value_raw = (value_raw or "").strip()
    if not value_raw:
        return None, None

    try:
        value = float(value_raw.replace(",", "."))
    except ValueError:
        return None, f"{field_label} inválido."

    return value, None


CADASTRO_SOLICITACAO_STATUS_VALIDOS = {"novo", "em_analise", "aprovado", "rejeitado"}
RESET_REQUEST_STATUS_VALIDOS = {
    RESET_REQUEST_STATUS_OPEN,
    RESET_REQUEST_STATUS_SENT,
    RESET_REQUEST_STATUS_DONE,
    RESET_REQUEST_STATUS_IGNORED,
}
MIN_USER_PASSWORD_LENGTH = 6
ADMIN_USER_ACTIONS = {"toggle_ativo", "reset_senha"}
ADMIN_LINK_STATUS_VALIDOS = {
    LINK_STATUS_AGUARDANDO_VERIFICACAO,
    LINK_STATUS_COMPRA_CONFIRMADA,
    LINK_STATUS_COMPRA_NAO_CONFIRMADA,
    LINK_STATUS_CASHBACK_PAGO,
}

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


@app.route("/admin/dashboard", methods=["GET"])
@login_required_admin
def admin_dashboard():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    dashboard_error = None
    summary = {}
    pending_links = []
    confirmed_links = []
    users_without_email = []
    last_diagnostic = None
    last_heartbeat = None

    try:
        summary = {
            "aguardando_verificacao": count_links_by_status("aguardando_verificacao"),
            "compra_confirmada": count_links_by_status("compra_confirmada"),
            "usuarios_sem_email": count_users_without_email(),
            "cadastros_pendentes": count_pending_signup_requests(),
            "reset_pendente": count_pending_password_reset_requests(),
        }
        pending_links = get_recent_links_by_status("aguardando_verificacao", limit=5)
        confirmed_links = get_recent_links_by_status("compra_confirmada", limit=5)
        users_without_email = get_users_without_email(limit=5)
        last_diagnostic = get_last_worker_diagnostic()
        last_heartbeat = get_last_worker_heartbeat()
    except Exception:
        app.logger.exception("[ADMIN DASHBOARD] Falha ao montar dados de resumo")
        dashboard_error = "Não foi possível carregar todos os dados do dashboard agora."

    robot_status = "Sem diagnóstico recente"
    if last_diagnostic and last_diagnostic["status"] == "ok":
        robot_status = "Robô funcionando"
    elif last_diagnostic:
        robot_status = "Atenção necessária"

    return render_template(
        "admin_dashboard.html",
        admin_username=session.get("admin_username"),
        dashboard_error=dashboard_error,
        summary=summary,
        pending_links=pending_links,
        confirmed_links=confirmed_links,
        users_without_email=users_without_email,
        robot_status=robot_status,
        last_diagnostic=last_diagnostic,
        last_heartbeat=last_heartbeat,
    )


@app.route("/admin/links", methods=["GET"])
@login_required_admin
def admin_links():
    if not admin_logado():
        return redirect(url_for("admin_login"))

    status = request.args.get("status", "").strip() or None
    codigo_usuario = request.args.get("codigo_usuario", "").strip() or None
    plataforma = request.args.get("plataforma", "").strip() or None
    descricao = request.args.get("descricao", "").strip() or request.args.get("q", "").strip() or None
    page = parse_positive_int(request.args.get("page"), 1)
    limit = parse_positive_int(request.args.get("limit"), 20)

    links, total = get_all_links(
        status=status,
        codigo_usuario=codigo_usuario,
        plataforma=plataforma,
        descricao=descricao,
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
        erro=request.args.get("erro", "").strip() or None,
        sucesso=request.args.get("sucesso", "").strip() or None,
        platform_labels=PLATFORM_LABELS,
        get_status_label=get_status_label,
        get_status_badge_class=get_status_badge_class,
        get_status_next_action=get_status_next_action,
        filtros={
            "status": status or "",
            "codigo_usuario": codigo_usuario or "",
            "plataforma": plataforma or "",
            "descricao": descricao or "",
        },
        email_status={
            "enabled": EMAIL_ENABLED,
            "from_email": SMTP_FROM_EMAIL or "Não configurado",
            "admin_email": ADMIN_NOTIFICATION_EMAIL or "Não configurado",
        },
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

    status_anterior = link["status"]
    status = request.form.get("status", "").strip() or None
    percentual_cashback_raw = request.form.get("percentual_cashback", "").strip()
    observacoes_admin = request.form.get("observacoes_admin", "").strip() or None
    descricao_item = request.form.get("descricao_item", "").strip() or None
    foto_item_url = request.form.get("foto_item_url", "").strip() or None
    valor_produto_raw = request.form.get("valor_produto", "").strip()
    percentual_comissao_raw = request.form.get("percentual_comissao", "").strip()
    acao = request.form.get("acao", "salvar").strip()

    if status and status not in ADMIN_LINK_STATUS_VALIDOS:
        return redirect(url_for("admin_links", erro="Status não permitido."))

    percentual_cashback, erro_cashback = parse_decimal_input(percentual_cashback_raw, "Cashback")
    if erro_cashback:
        return redirect(url_for("admin_links", erro=erro_cashback))
    if percentual_cashback is not None and not (0 <= percentual_cashback <= 100):
        return redirect(url_for("admin_links", erro="Cashback deve estar entre 0 e 100."))

    valor_produto, erro_valor_produto = parse_decimal_input(valor_produto_raw, "Valor do produto")
    if erro_valor_produto:
        return redirect(url_for("admin_links", erro=erro_valor_produto))
    if valor_produto is not None and valor_produto < 0:
        return redirect(url_for("admin_links", erro="Valor do produto deve ser maior ou igual a 0."))

    percentual_comissao, erro_percentual_comissao = parse_decimal_input(percentual_comissao_raw, "Percentual de comissão")
    if erro_percentual_comissao:
        return redirect(url_for("admin_links", erro=erro_percentual_comissao))
    if percentual_comissao is not None and not (0 <= percentual_comissao <= 100):
        return redirect(url_for("admin_links", erro="Percentual de comissão deve estar entre 0 e 100."))

    atualizado_em = now_str()

    update_product_metadata(
        link_id=link_id,
        descricao_item=descricao_item,
        foto_item_url=foto_item_url,
        valor_produto=valor_produto,
        percentual_comissao=percentual_comissao,
        atualizado_em=atualizado_em,
    )

    update_link_admin_fields(
        link_id=link_id,
        status=status,
        percentual_cashback=percentual_cashback,
        observacoes_admin=observacoes_admin,
        atualizado_em=atualizado_em
    )
    recalcular_valores(
        link_id=link_id,
        percentual_cashback=percentual_cashback,
        atualizado_em=atualizado_em,
    )

    mensagem_sucesso = "Link atualizado com sucesso."
    status_novo = status or status_anterior
    if status_novo != status_anterior:
        usuario = get_user_by_id(link["usuario_id"])
        email_result = {"ok": True}
        if status_novo == LINK_STATUS_COMPRA_CONFIRMADA:
            email_result = notify_user_purchase_confirmed(usuario, get_link_by_id(link_id))
        elif status_novo == LINK_STATUS_COMPRA_NAO_CONFIRMADA:
            email_result = notify_user_purchase_not_confirmed(usuario, get_link_by_id(link_id))
        elif status_novo == LINK_STATUS_CASHBACK_PAGO:
            email_result = notify_user_cashback_paid(usuario, get_link_by_id(link_id))

        if not email_result.get("ok") and status_novo in {
            LINK_STATUS_COMPRA_CONFIRMADA,
            LINK_STATUS_COMPRA_NAO_CONFIRMADA,
            LINK_STATUS_CASHBACK_PAGO,
        }:
            app.logger.warning("[EMAIL_USER] falha controlada ao enviar após atualizar link_id=%s", link_id)
            mensagem_sucesso = "Link atualizado com sucesso. Status salvo, mas e-mail não foi enviado."

    return redirect(url_for("admin_links", sucesso=mensagem_sucesso))


@app.route("/admin/links/<int:link_id>/atualizar-infos", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_atualizar_infos_link(link_id):
    if not admin_logado():
        return jsonify({"ok": False, "erro": "Admin não autenticado."}), 401

    link = get_link_by_id(link_id)
    if not link:
        return jsonify({"ok": False, "erro": "Link não encontrado."}), 404

    reenfileirar_metadados(
        link_id=link_id,
        atualizado_em=now_str(),
    )
    app.logger.info("[ADMIN] Reprocessamento de metadados enfileirado para link_id=%s", link_id)
    return jsonify({
        "ok": True,
        "link_id": link_id,
        "metadados_status": "pendente",
        "mensagem": "Item enviado para atualização de informações.",
    })


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

    status_anterior = solicitacao["status"]
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

    if status != status_anterior:
        if status == "aprovado":
            usuario = get_user_by_email((solicitacao["email"] or "").strip())
            email_result = notify_user_signup_approved(usuario, solicitacao)
            if not email_result.get("ok"):
                app.logger.warning("[EMAIL_USER] falha controlada ao enviar após aprovação da solicitação_id=%s", solicitacao_id)
        elif status == "rejeitado":
            email_result = notify_user_signup_rejected(solicitacao, motivo=observacoes_admin)
            if not email_result.get("ok"):
                app.logger.warning("[EMAIL_USER] falha controlada ao enviar após rejeição da solicitação_id=%s", solicitacao_id)

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
                "email": request.args.get("email", "").strip(),
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
    email = request.form.get("email", "").strip().lower() or None
    aprovar_solicitacao = request.form.get("aprovar_solicitacao") == "on"

    erro = None

    if not nome:
        erro = "Nome é obrigatório."
    elif not codigo_usuario:
        erro = "Código do usuário é obrigatório."
    elif get_user_by_codigo_any_status(codigo_usuario):
        erro = "Código do usuário já existe."
    elif email and not is_valid_email(email):
        erro = "Informe um e-mail válido."
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
                "email": email or "",
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
        email=email,
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
            "email": "",
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

    q = (request.args.get("q", "") or "").strip()
    email_status = (request.args.get("email_status", "todos") or "todos").strip().lower()
    status = (request.args.get("status", "todos") or "todos").strip().lower()
    senha_status = (request.args.get("senha_status", "todos") or "todos").strip().lower()

    allowed_email_status = {"todos", "sem_email", "com_email"}
    allowed_status = {"todos", "ativo", "inativo"}
    allowed_senha_status = {"todos", "troca_pendente", "senha_definida"}

    if email_status not in allowed_email_status:
        email_status = "todos"
    if status not in allowed_status:
        status = "todos"
    if senha_status not in allowed_senha_status:
        senha_status = "todos"

    usuarios = list_users_admin(
        q=q or None,
        email_status=email_status,
        status=status,
        senha_status=senha_status,
    )

    sem_email_count = sum(1 for u in usuarios if not (u["email"] or "").strip())
    inativos_count = sum(1 for u in usuarios if not u["ativo"])
    troca_pendente_count = sum(1 for u in usuarios if u["must_change_password"])

    return render_template(
        "admin_usuarios.html",
        admin_username=session.get("admin_username"),
        usuarios=usuarios,
        filtros={
            "q": q,
            "email_status": email_status,
            "status": status,
            "senha_status": senha_status,
        },
        resumo={
            "total": len(usuarios),
            "sem_email": sem_email_count,
            "inativos": inativos_count,
            "troca_pendente": troca_pendente_count,
        },
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


@app.route("/admin/usuarios/<int:user_id>/email", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_atualizar_usuario_email(user_id):
    if not admin_logado():
        return redirect(url_for("admin_login"))

    usuario = get_user_by_id(user_id)
    if not usuario:
        return redirect(url_for("admin_usuarios", erro="Usuário não encontrado."))

    email_raw = request.form.get("email", "")
    email_normalizado = (email_raw or "").strip().lower()
    email_final = email_normalizado or None

    if email_final and not is_valid_email(email_final):
        return redirect(url_for("admin_usuarios", erro="Informe um e-mail válido."))

    update_user_email(user_id=user_id, email=email_final)
    return redirect(url_for("admin_usuarios", sucesso="E-mail atualizado com sucesso."))


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
    provided_token = (token or "").strip()
    return bool(configured_token) and bool(provided_token) and hmac.compare_digest(provided_token, configured_token)


def validate_worker_request():
    worker_token = request.headers.get("X-Worker-Token", "").strip()
    worker_id = request.headers.get("X-Worker-Id", "").strip() or "desconhecido"

    if not WORKER_ENABLED:
        return jsonify({"ok": False, "erro": "Worker desabilitado."}), 503

    if not worker_token:
        app.logger.warning(
            "[WORKER AUTH] Token ausente | worker_id=%s | ip=%s | path=%s",
            worker_id,
            get_client_ip(),
            request.path,
        )
        return jsonify({"ok": False, "erro": "Não autorizado."}), 401

    if not worker_token_is_valid(worker_token):
        app.logger.warning(
            "[WORKER AUTH] Token inválido | worker_id=%s | ip=%s | path=%s",
            worker_id,
            get_client_ip(),
            request.path,
        )
        return jsonify({"ok": False, "erro": "Não autorizado."}), 401

    return None




@app.route("/api/extension/status", methods=["GET"])
def extension_status():
    return jsonify(build_extension_status_response(session))


@app.route("/api/extension/product-preview", methods=["POST"])
def extension_product_preview():
    data = request.get_json(silent=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"ok": False, "erro": "URL é obrigatória."}), 400

    return jsonify(build_product_preview(raw_url))

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

    criado_em = now_str()
    try:
        solicitacao_id = create_cadastro_solicitacao(
            nome_completo=nome_completo,
            email=email,
            codigo_indicacao=codigo_indicacao,
            whatsapp=None,
            status="novo",
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
        notify_admin_new_signup_request({
            "id": solicitacao_id,
            "nome_completo": nome_completo,
            "email": email,
            "codigo_indicacao": codigo_indicacao,
            "whatsapp": None,
            "criado_em": criado_em,
        })
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
    data = request.get_json(silent=True) or {}
    identificador = (data.get("identificador") or data.get("codigo_usuario") or "")
    identificador_normalizado = identificador.strip().lower()
    if not identificador_normalizado:
        return jsonify({"ok": False, "erro": "Informe o código do usuário ou e-mail."}), 400

    identificador_hash = hashlib.sha256(identificador_normalizado.encode("utf-8")).hexdigest()
    ip_solicitante = get_client_ip()
    limite_identificador = count_recent_attempts_by_identifier(identificador_hash, minutes=30)
    limite_ip = count_recent_attempts_by_ip(ip_solicitante, minutes=30)

    if limite_identificador >= 3 or limite_ip >= 10:
        create_password_reset_attempt(
            ip=ip_solicitante,
            identificador_hash=identificador_hash,
            usuario_id=None,
            permitido=False,
            motivo="rate_limit",
            criado_em=now_str(),
        )
        app.logger.warning(
            "[RESET_RATE_LIMIT] bloqueado por identificador_hash=%s ip=%s",
            identificador_hash,
            ip_solicitante,
        )
        return jsonify({"ok": False, "erro": "Muitas solicitações foram feitas. Aguarde alguns minutos e tente novamente."}), 429

    mensagem_generica = "Se os dados estiverem corretos, enviaremos instruções para o e-mail cadastrado."
    usuario = get_user_by_codigo_or_email(identificador_normalizado)
    usuario_id = usuario["id"] if usuario else None
    create_password_reset_attempt(
        ip=ip_solicitante,
        identificador_hash=identificador_hash,
        usuario_id=usuario_id,
        permitido=True,
        motivo="ok",
        criado_em=now_str(),
    )
    app.logger.info(
        "[RESET_RATE_LIMIT] tentativa registrada ip=%s permitido=1 motivo=ok identificador_hash=%s",
        ip_solicitante,
        identificador_hash,
    )

    if not usuario or not usuario["ativo"]:
        return jsonify({"ok": True, "message": mensagem_generica}), 200

    email = (usuario["email"] or "").strip() if "email" in usuario.keys() else ""
    if not email:
        return jsonify({"ok": False, "erro": "Este usuário não possui e-mail cadastrado. Entre em contato com o suporte."}), 400

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    criado_em = now_str()
    expira_em = (datetime.now() + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S")
    invalidate_active_tokens_for_user(usuario["id"])
    create_password_reset_token(usuario["id"], email, token_hash, criado_em, expira_em, get_client_ip(), request.headers.get("User-Agent", "")[:255])

    reset_url = f"https://minhaoferta.com/redefinir-senha?token={token}"
    envio = send_password_reset_email(usuario, reset_url)
    if not envio.get("ok"):
        invalidate_active_tokens_for_user(usuario["id"])
        return jsonify({"ok": False, "erro": envio.get("message", "Falha ao enviar e-mail.")}), 503

    app.logger.info("[RESET_RATE_LIMIT] reset permitido usuario_id=%s ip=%s", usuario["id"], ip_solicitante)
    return jsonify({"ok": True, "message": mensagem_generica}), 200


@app.route("/redefinir-senha", methods=["GET"])
def pagina_redefinir_senha():
    token = request.args.get("token", "").strip()
    return render_template("redefinir_senha.html", token=token)


@app.route("/api/redefinir-senha", methods=["POST"])
def redefinir_senha_com_token():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    nova_senha = data.get("nova_senha", "")
    confirmar_senha = data.get("confirmar_senha", "")

    if not token:
        return jsonify({"ok": False, "erro": "Link inválido ou expirado."}), 400
    if len(nova_senha) < MIN_USER_PASSWORD_LENGTH:
        return jsonify({"ok": False, "erro": f"A nova senha deve ter no mínimo {MIN_USER_PASSWORD_LENGTH} caracteres."}), 400
    if nova_senha != confirmar_senha:
        return jsonify({"ok": False, "erro": "A confirmação da nova senha não confere."}), 400

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    token_row = get_valid_reset_token(token_hash, now_str())
    if not token_row:
        return jsonify({"ok": False, "erro": "Link inválido ou expirado."}), 400

    update_user_password(user_id=token_row["usuario_id"], password=nova_senha, must_change_password=0)
    mark_reset_token_used(token_row["id"], now_str())
    return jsonify({"ok": True, "message": "Senha redefinida com sucesso.", "redirect_to": url_for("pagina_inicial")})


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
            "erro": "No momento aceitamos apenas links do Mercado Livre."
        }), 400

    if plataforma != PLATFORM_MERCADOLIVRE:
        return jsonify({
            "ok": False,
            "erro": "No momento aceitamos apenas links do Mercado Livre."
        }), 400

    app.logger.info("[MARKETPLACE DETECTADO] %s | url=%s", plataforma, url)

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
            "status_label": get_status_label(job["status"], context="user"),
            "status_badge_class": get_status_badge_class(job["status"]),
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

    criado_em = now_str()
    create_link_gerado(
        usuario_id=job["usuario_id"],
        job_id=job_id,
        url_original=job["url_original"],
        plataforma=job["plataforma"] or PLATFORM_MERCADOLIVRE,
        url_afiliado=url_afiliado,
        status=LINK_STATUS_AGUARDANDO_VERIFICACAO,
        percentual_cashback=CASHBACK_PERCENTUAL_PADRAO,
        criado_em=criado_em,
        atualizado_em=criado_em,
    )
    app.logger.info("[JOB %s] Link afiliado persistido e job concluído.", job_id)

    usuario = get_user_by_id(job["usuario_id"])
    notify_admin_new_link_pending({
        "usuario_nome": (usuario["nome"] if usuario and "nome" in usuario.keys() else None),
        "codigo_usuario": (usuario["codigo_usuario"] if usuario and "codigo_usuario" in usuario.keys() else None),
        "descricao_item": None,
        "url_original": job["url_original"],
        "url_afiliado": url_afiliado,
        "status": LINK_STATUS_AGUARDANDO_VERIFICACAO,
        "criado_em": criado_em,
    })

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




@app.route("/api/admin/email/test", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_email_test():
    if not admin_logado():
        return jsonify({"ok": False, "message": "Admin não autenticado."}), 401

    result = send_test_email()
    status_code = 200 if result.get("ok") else 400
    return jsonify({
        "ok": bool(result.get("ok")),
        "message": result.get("message", "Falha ao enviar e-mail de teste."),
    }), status_code

@app.route("/api/admin/worker-healthcheck/run", methods=["POST"])
@login_required_admin
@csrf_protected
def admin_run_worker_healthcheck():
    worker_id = request.json.get("worker_id", "").strip() if request.is_json else ""
    diagnostic_id = create_diagnostic(
        worker_id=worker_id or None,
        status="executando",
        etapa="solicitado",
        mensagem="Health check solicitado pelo admin.",
        criado_em=now_str(),
    )
    app.logger.info("[HEALTHCHECK] solicitado | diagnostic_id=%s | worker_id=%s", diagnostic_id, worker_id or "*")
    return jsonify({"ok": True, "diagnostic_id": diagnostic_id})


@app.route("/api/admin/worker-healthcheck/logs", methods=["GET"])
@login_required_admin
def admin_worker_healthcheck_logs():
    rows = get_last_diagnostics(limit=20)
    return jsonify({
        "ok": True,
        "logs": [
            {
                "id": row["id"],
                "worker_id": row["worker_id"],
                "status": row["status"],
                "label": get_status_label(row["status"], context="worker"),
                "etapa": row["etapa"],
                "mensagem": row["mensagem"],
                "detalhes": row["detalhes"],
                "iniciou_em": row["iniciou_em"],
                "finalizou_em": row["finalizou_em"],
                "duracao_ms": row["duracao_ms"],
                "criado_em": row["criado_em"],
            } for row in rows
        ]
    })


@app.route("/api/worker/healthcheck/claim", methods=["POST"])
def worker_claim_healthcheck():
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error
    worker_id = get_request_worker_id(request.get_json(silent=True) or {})
    if not worker_id:
        return jsonify({"ok": False, "erro": "worker_id não informado."}), 400
    diag = claim_pending_diagnostic(worker_id=worker_id, claimed_em=now_str())
    return jsonify({
        "ok": True,
        "diagnostic": None if not diag else {
            "id": diag["id"],
            "worker_id": diag["worker_id"],
            "status": diag["status"],
            "etapa": diag["etapa"],
            "mensagem": diag["mensagem"],
            "iniciou_em": diag["iniciou_em"],
            "criado_em": diag["criado_em"],
        }
    })


@app.route("/api/worker/healthcheck/<int:diagnostic_id>/success", methods=["POST"])
def worker_healthcheck_success(diagnostic_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    update_diagnostic(
        diagnostic_id,
        status="ok",
        etapa=data.get("etapa", "finalizado"),
        mensagem=(data.get("mensagem") or "Health check concluído com sucesso.")[:500],
        detalhes=(data.get("detalhes") or "")[:1000] or None,
        finalizou_em=now_str(),
        duracao_ms=data.get("duracao_ms"),
    )
    return jsonify({"ok": True})


@app.route("/api/worker/healthcheck/<int:diagnostic_id>/error", methods=["POST"])
def worker_healthcheck_error(diagnostic_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    update_diagnostic(
        diagnostic_id,
        status="erro",
        etapa=data.get("etapa", "finalizado"),
        mensagem=(data.get("mensagem") or "Health check concluído com erro.")[:500],
        detalhes=(data.get("detalhes") or "")[:1000] or None,
        finalizou_em=now_str(),
        duracao_ms=data.get("duracao_ms"),
    )
    return jsonify({"ok": True})


@app.route("/api/worker/metadata/claim", methods=["POST"])
def worker_claim_metadata_job():
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    metadata_job = claim_next_metadata_job(atualizado_em=now_str())
    if not metadata_job:
        return jsonify({"ok": True, "metadata_job": None})

    app.logger.info(
        "[METADATA %s] Job de metadados claimado para processamento.",
        metadata_job["id"],
    )
    return jsonify({
        "ok": True,
        "metadata_job": {
            "id": metadata_job["id"],
            "job_id": metadata_job["job_id"],
            "usuario_id": metadata_job["usuario_id"],
            "url_original": metadata_job["url_original"],
            "percentual_cashback": metadata_job["percentual_cashback"],
        }
    })


@app.route("/api/worker/metadata/<int:link_id>/success", methods=["POST"])
def worker_metadata_success(link_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    descricao_item = data.get("descricao_item")
    foto_item_url = data.get("foto_item_url")
    valor_produto = data.get("valor_produto")
    percentual_comissao = data.get("percentual_comissao")
    percentual_cashback = data.get("percentual_cashback")

    link = get_link_by_id(link_id)
    if not link:
        return jsonify({"ok": False, "erro": "Link não encontrado."}), 404
    if link["metadados_status"] not in {"pendente", "processando"}:
        return jsonify({"ok": False, "erro": "Link fora de contexto para metadados success."}), 409

    atualizado_em = now_str()
    update_product_metadata(
        link_id=link_id,
        descricao_item=descricao_item,
        foto_item_url=foto_item_url,
        valor_produto=valor_produto,
        percentual_comissao=percentual_comissao,
        metadados_status="concluido",
        metadados_erro="",
        metadados_atualizado_em=atualizado_em,
        atualizado_em=atualizado_em,
    )
    recalcular_valores(
        link_id=link_id,
        percentual_cashback=percentual_cashback,
        atualizado_em=atualizado_em,
    )
    app.logger.info("[METADATA %s] Metadados concluídos com sucesso.", link_id)
    return jsonify({"ok": True, "link_id": link_id, "metadados_status": "concluido"})


@app.route("/api/worker/metadata/<int:link_id>/error", methods=["POST"])
def worker_metadata_error(link_id):
    auth_error = validate_worker_request()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    mensagem_erro = data.get("mensagem_erro", "").strip()
    if not mensagem_erro:
        return jsonify({"ok": False, "erro": "mensagem_erro não informada."}), 400

    link = get_link_by_id(link_id)
    if not link:
        return jsonify({"ok": False, "erro": "Link não encontrado."}), 404

    if link["metadados_status"] not in {"pendente", "processando"}:
        return jsonify({"ok": False, "erro": "Link fora de contexto para metadados error."}), 409

    atualizado_em = now_str()
    update_product_metadata(
        link_id=link_id,
        metadados_status="erro",
        metadados_erro=mensagem_erro,
        metadados_atualizado_em=atualizado_em,
        atualizado_em=atualizado_em,
    )
    app.logger.warning("[METADATA %s] Erro no processamento: %s", link_id, mensagem_erro)
    return jsonify({"ok": True, "link_id": link_id, "metadados_status": "erro"})


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
            "status_label": get_status_label(job["status"], context="user"),
            "status_badge_class": get_status_badge_class(job["status"]),
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

    try:
        links = get_links_by_usuario_id(usuario["id"])
        links_payload = []
        for link in links:
            status = link["status"] if "status" in link.keys() else None
            links_payload.append({
                "id": link["id"],
                "job_id": link["job_id"],
                "url_afiliado": link["url_afiliado"],
                "plataforma": link["plataforma"],
                "plataforma_label": get_platform_label(link["plataforma"]),
                "status": status,
                "status_label": get_status_label(status, context="user"),
                "status_description": get_status_description(status, context="user"),
                "status_badge_class": get_status_badge_class(status),
                "descricao_item": link["descricao_item"],
                "foto_item_url": link["foto_item_url"],
                "valor_cashback": link["valor_cashback"],
                "criado_em": link["criado_em"],
            })
    except Exception:
        app.logger.exception("[HISTORICO] Falha ao montar payload de links para %s", codigo_usuario)
        return jsonify({
            "ok": False,
            "erro": "Não foi possível carregar o histórico no momento. Tente novamente em instantes."
        }), 500

    return jsonify({
        "ok": True,
        "usuario": {
            "id": usuario["id"],
            "codigo_usuario": usuario["codigo_usuario"],
            "nome": usuario["nome"]
        },
        "links": links_payload
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
            "label": get_status_label(status, context="worker"),
            "next_action": get_status_next_action(status, context="worker"),
            "message": message,
        }
    })


if __name__ == "__main__":
    host = HOST or "0.0.0.0"
    app.logger.info(f"Iniciando servidor Flask em {host}:{PORT}")
    app.run(host=host, port=PORT, debug=DEBUG)
