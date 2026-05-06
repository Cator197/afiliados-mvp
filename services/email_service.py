import smtplib
from email.message import EmailMessage

from flask import current_app

from config import (
    ADMIN_NOTIFICATION_EMAIL,
    EMAIL_ENABLED,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USER,
)


def _safe_field(value, fallback="não informado"):
    raw = "" if value is None else str(value).strip()
    return raw or fallback


def _get_field(obj, field, default=""):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field, default)
    try:
        return obj[field]
    except Exception:
        return default


def _missing_config_fields() -> list[str]:
    missing = []
    if not SMTP_HOST:
        missing.append("SMTP_HOST")
    if not SMTP_USER:
        missing.append("SMTP_USER")
    if not SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if not SMTP_FROM_EMAIL:
        missing.append("SMTP_FROM_EMAIL")
    return missing


def send_email(to, subject, body_text=None, body_html=None, reply_to=None):
    to = (to or "").strip()
    subject = (subject or "").strip()

    if not EMAIL_ENABLED:
        current_app.logger.info("[EMAIL] envio ignorado: EMAIL_ENABLED=false")
        return {"ok": False, "message": "Envio de e-mail desativado."}

    missing = _missing_config_fields()
    if missing:
        current_app.logger.warning("[EMAIL] configuração SMTP incompleta: %s", ", ".join(missing))
        return {"ok": False, "message": "Configuração de e-mail incompleta."}

    if not to:
        return {"ok": False, "message": "Destinatário de e-mail não informado."}
    if not subject:
        return {"ok": False, "message": "Assunto de e-mail não informado."}

    current_app.logger.info("[EMAIL] tentativa de envio para=%s assunto=%s", to, subject)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>" if SMTP_FROM_NAME else SMTP_FROM_EMAIL
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to

    plain_body = (body_text or "").strip() or "Mensagem enviada pelo sistema Minha Oferta."
    msg.set_content(plain_body)

    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        if SMTP_USE_SSL:
            smtp_client = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
        else:
            smtp_client = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)

        with smtp_client as server:
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        current_app.logger.info("[EMAIL] envio realizado com sucesso para=%s", to)
        return {"ok": True, "message": "E-mail enviado com sucesso."}
    except Exception as exc:
        current_app.logger.exception("[EMAIL] falha controlada no envio para=%s: %s", to, exc.__class__.__name__)
        return {"ok": False, "message": "Falha ao enviar e-mail. Verifique a configuração SMTP."}


def send_test_email(to=None):
    target = (to or ADMIN_NOTIFICATION_EMAIL or "").strip()
    if not target:
        return {"ok": False, "message": "E-mail de destino do admin não configurado."}

    subject = "Teste de e-mail - Minha Oferta"
    body_text = (
        "Este é um e-mail de teste do sistema Minha Oferta.\n\n"
        "Se você recebeu esta mensagem, a configuração SMTP está funcionando."
    )

    body_html = (
        "<p>Este é um e-mail de teste do sistema <strong>Minha Oferta</strong>.</p>"
        "<p>Se você recebeu esta mensagem, a configuração SMTP está funcionando.</p>"
    )

    return send_email(to=target, subject=subject, body_text=body_text, body_html=body_html)


def notify_admin_new_signup_request(solicitacao):
    try:
        if not EMAIL_ENABLED:
            current_app.logger.info("[EMAIL_NOTIFY] notificação de cadastro ignorada: EMAIL_ENABLED=false")
            return {"ok": False, "message": "Envio de e-mail desativado."}

        target = (ADMIN_NOTIFICATION_EMAIL or "").strip()
        if not target:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar cadastro: ADMIN_NOTIFICATION_EMAIL ausente")
            return {"ok": False, "message": "E-mail do admin não configurado."}

        subject = "Nova solicitação de cadastro - Minha Oferta"
        body_text = (
            "Olá,\n\n"
            "Uma nova solicitação de cadastro foi recebida no Minha Oferta.\n\n"
            f"Nome: {_safe_field(_get_field(solicitacao, 'nome_completo'))}\n"
            f"E-mail: {_safe_field(_get_field(solicitacao, 'email'))}\n"
            f"Telefone/WhatsApp: {_safe_field(_get_field(solicitacao, 'whatsapp'))}\n"
            f"Código desejado: {_safe_field(_get_field(solicitacao, 'codigo_indicacao'))}\n"
            f"Data: {_safe_field(_get_field(solicitacao, 'criado_em'))}\n\n"
            "Acesse o painel admin para analisar:\n"
            "https://minhaoferta.com/admin/solicitacoes"
        )
        result = send_email(to=target, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_NOTIFY] notificação de cadastro enviada")
        else:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar cadastro: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar cadastro: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao notificar cadastro."}


def notify_admin_password_reset_request(reset_request):
    try:
        if not EMAIL_ENABLED:
            current_app.logger.info("[EMAIL_NOTIFY] notificação de reset ignorada: EMAIL_ENABLED=false")
            return {"ok": False, "message": "Envio de e-mail desativado."}

        target = (ADMIN_NOTIFICATION_EMAIL or "").strip()
        if not target:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar reset: ADMIN_NOTIFICATION_EMAIL ausente")
            return {"ok": False, "message": "E-mail do admin não configurado."}

        subject = "Solicitação de recuperação de senha - Minha Oferta"
        body_text = (
            "Olá,\n\n"
            "Um usuário solicitou recuperação de senha.\n\n"
            f"Código do usuário: {_safe_field(_get_field(reset_request, 'codigo_usuario'))}\n"
            f"E-mail informado: {_safe_field(_get_field(reset_request, 'email'))}\n"
            f"Data: {_safe_field(_get_field(reset_request, 'criado_em'))}\n\n"
            "Acesse o painel admin para analisar:\n"
            "https://minhaoferta.com/admin/reset-senhas\n\n"
            "Observação: este fluxo continua manual/admin neste PR."
        )
        result = send_email(to=target, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_NOTIFY] notificação de reset enviada")
        else:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar reset: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar reset: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao notificar reset."}


def notify_admin_new_link_pending(link):
    try:
        if not EMAIL_ENABLED:
            current_app.logger.info("[EMAIL_NOTIFY] notificação de link ignorada: EMAIL_ENABLED=false")
            return {"ok": False, "message": "Envio de e-mail desativado."}

        target = (ADMIN_NOTIFICATION_EMAIL or "").strip()
        if not target:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar link: ADMIN_NOTIFICATION_EMAIL ausente")
            return {"ok": False, "message": "E-mail do admin não configurado."}

        subject = "Novo link aguardando verificação - Minha Oferta"
        descricao = _safe_field(_get_field(link, 'descricao_item'), fallback='Descrição ainda não atualizada')
        body_text = (
            "Olá,\n\n"
            "Um novo link foi gerado e está aguardando verificação.\n\n"
            f"Usuário: {_safe_field(_get_field(link, 'usuario_nome'))}\n"
            f"Código do usuário: {_safe_field(_get_field(link, 'codigo_usuario'))}\n"
            f"Descrição/produto: {descricao}\n"
            f"URL original: {_safe_field(_get_field(link, 'url_original'))}\n"
            f"Link afiliado: {_safe_field(_get_field(link, 'url_afiliado'))}\n"
            f"Status: {_safe_field(_get_field(link, 'status'))}\n"
            f"Data: {_safe_field(_get_field(link, 'criado_em'))}\n\n"
            "Acesse o painel admin:\n"
            "https://minhaoferta.com/admin/links"
        )
        result = send_email(to=target, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_NOTIFY] notificação de link enviado")
        else:
            current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar link: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_NOTIFY] falha ao notificar link: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao notificar link."}


def send_password_reset_email(user, reset_url: str):
    email = (_get_field(user, "email") or "").strip()
    if not email:
        return {"ok": False, "message": "Usuário sem e-mail cadastrado."}

    nome = (_get_field(user, "nome") or "").strip()
    codigo = (_get_field(user, "codigo_usuario") or "").strip()
    saudacao = nome or codigo or "usuário"

    subject = "Recuperação de senha - Minha Oferta"
    body_text = (
        f"Olá, {saudacao}\n\n"
        "Recebemos uma solicitação para redefinir sua senha no Minha Oferta.\n\n"
        "Clique no link abaixo para criar uma nova senha:\n"
        f"{reset_url}\n\n"
        "Este link expira em 60 minutos.\n"
        "Se você não solicitou isso, ignore este e-mail."
    )
    body_html = (
        f"<p>Olá, {saudacao}</p>"
        "<p>Recebemos uma solicitação para redefinir sua senha no Minha Oferta.</p>"
        f"<p><a href=\"{reset_url}\">Clique no link para criar uma nova senha</a></p>"
        "<p>Este link expira em 60 minutos.<br>Se você não solicitou isso, ignore este e-mail.</p>"
    )
    return send_email(to=email, subject=subject, body_text=body_text, body_html=body_html)


def _user_history_url(user):
    codigo_usuario = (_get_field(user, "codigo_usuario") or "").strip()
    if codigo_usuario:
        return f"https://minhaoferta.com/historico/{codigo_usuario}"
    return "https://minhaoferta.com/login"


def _format_cashback_value(link):
    valor_cashback = _get_field(link, "valor_cashback")
    if valor_cashback is None:
        return "Aguardando cálculo"
    try:
        return f"{float(valor_cashback):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "Aguardando cálculo"


def notify_user_signup_approved(user, solicitacao=None):
    try:
        email = (_get_field(user, "email") or _get_field(solicitacao, "email") or "").strip()
        if not email:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: usuário sem e-mail cadastrado")
            return {"ok": False, "message": "Usuário sem e-mail cadastrado"}

        nome = (_get_field(user, "nome") or _get_field(solicitacao, "nome_completo") or "").strip()
        saudacao = f"Olá, {nome}." if nome else "Olá."
        subject = "Cadastro aprovado - Minha Oferta"
        body_text = (
            f"{saudacao}\n\n"
            "Seu cadastro no Minha Oferta foi aprovado.\n\n"
            "Agora você já pode acessar sua conta e gerar links de compra com cashback.\n\n"
            "Acesse:\n"
            "https://minhaoferta.com/login\n\n"
            "Se você não solicitou esse cadastro, ignore este e-mail."
        )
        result = send_email(to=email, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_USER] cadastro aprovado enviado")
        else:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao enviar e-mail."}


def notify_user_signup_rejected(solicitacao, motivo=None):
    try:
        email = (_get_field(solicitacao, "email") or "").strip()
        if not email:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: usuário sem e-mail cadastrado")
            return {"ok": False, "message": "Usuário sem e-mail cadastrado"}

        detalhe = ""
        if motivo:
            detalhe = f"\n\nObservação: {(str(motivo) or '').strip()}"

        subject = "Atualização sobre sua solicitação de cadastro - Minha Oferta"
        body_text = (
            "Olá.\n\n"
            "Sua solicitação de cadastro no Minha Oferta foi analisada, mas não foi aprovada neste momento.\n\n"
            "Se quiser mais informações, entre em contato com nosso suporte."
            f"{detalhe}"
        )
        result = send_email(to=email, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_USER] cadastro rejeitado enviado")
        else:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao enviar e-mail."}


def notify_user_purchase_confirmed(user, link):
    try:
        email = (_get_field(user, "email") or "").strip()
        if not email:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: usuário sem e-mail cadastrado")
            return {"ok": False, "message": "Usuário sem e-mail cadastrado"}
        nome = (_get_field(user, "nome") or "").strip()
        saudacao = f"Olá, {nome}." if nome else "Olá."
        descricao = (_get_field(link, "descricao_item") or "").strip() or "Produto não identificado"
        valor_cashback = _format_cashback_value(link)
        subject = "Compra confirmada - Cashback em preparação"
        body_text = (
            f"{saudacao}\n\n"
            "Sua compra foi confirmada no Minha Oferta.\n\n"
            f"Produto: {descricao}\n"
            f"Cashback previsto: R$ {valor_cashback}\n\n"
            "Agora o cashback está em preparação para pagamento.\n\n"
            "Acompanhe seu histórico:\n"
            f"{_user_history_url(user)}"
        )
        result = send_email(to=email, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_USER] compra confirmada enviada")
        else:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao enviar e-mail."}


def notify_user_purchase_not_confirmed(user, link):
    try:
        email = (_get_field(user, "email") or "").strip()
        if not email:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: usuário sem e-mail cadastrado")
            return {"ok": False, "message": "Usuário sem e-mail cadastrado"}
        nome = (_get_field(user, "nome") or "").strip()
        saudacao = f"Olá, {nome}." if nome else "Olá."
        descricao = (_get_field(link, "descricao_item") or "").strip() or "Produto não identificado"
        subject = "Compra não confirmada - Minha Oferta"
        body_text = (
            f"{saudacao}\n\n"
            "Não conseguimos confirmar a compra relacionada a este link.\n\n"
            f"Produto: {descricao}\n"
            "Status: Compra não confirmada\n\n"
            "Isso pode acontecer quando a compra não foi feita pelo link gerado, foi cancelada ou não foi identificada pela plataforma.\n\n"
            "Acompanhe seu histórico:\n"
            f"{_user_history_url(user)}"
        )
        result = send_email(to=email, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_USER] compra não confirmada enviada")
        else:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao enviar e-mail."}


def notify_user_cashback_paid(user, link):
    try:
        email = (_get_field(user, "email") or "").strip()
        if not email:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: usuário sem e-mail cadastrado")
            return {"ok": False, "message": "Usuário sem e-mail cadastrado"}
        nome = (_get_field(user, "nome") or "").strip()
        saudacao = f"Olá, {nome}." if nome else "Olá."
        descricao = (_get_field(link, "descricao_item") or "").strip() or "Produto não identificado"
        valor_cashback = _format_cashback_value(link)
        subject = "Cashback pago - Minha Oferta"
        body_text = (
            f"{saudacao}\n\n"
            "O cashback de uma compra foi marcado como pago.\n\n"
            f"Produto: {descricao}\n"
            f"Valor do cashback: R$ {valor_cashback}\n\n"
            "Obrigado por usar o Minha Oferta.\n\n"
            "Acompanhe seu histórico:\n"
            f"{_user_history_url(user)}"
        )
        result = send_email(to=email, subject=subject, body_text=body_text)
        if result.get("ok"):
            current_app.logger.info("[EMAIL_USER] cashback pago enviado")
        else:
            current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", result.get("message", "erro desconhecido"))
        return result
    except Exception as exc:
        current_app.logger.warning("[EMAIL_USER] falha controlada ao enviar: %s", exc.__class__.__name__)
        return {"ok": False, "message": "Falha controlada ao enviar e-mail."}
