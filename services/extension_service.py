from urllib.parse import urlparse

from flask import url_for

PLATFORM_MERCADOLIVRE = "mercadolivre"
EXTENSION_ESTIMATED_CASHBACK_PERCENT = 3
ALLOWED_MERCADOLIVRE_HOSTS = {"mercadolivre.com.br", "www.mercadolivre.com.br"}


def get_current_user_from_session(session_obj):
    if not session_obj.get("user_logged_in"):
        return None

    user_id = session_obj.get("user_id")
    codigo_usuario = session_obj.get("codigo_usuario")
    nome = session_obj.get("user_nome")

    if not user_id or not codigo_usuario:
        return None

    return {
        "id": user_id,
        "codigo_usuario": codigo_usuario,
        "nome": nome,
    }


def build_extension_status_response(session_obj):
    user = get_current_user_from_session(session_obj)
    login_url = url_for("pagina_inicial", _external=True)

    if not user:
        return {
            "logged_in": False,
            "user": None,
            "login_url": login_url,
            "historico_url": None,
        }

    return {
        "logged_in": True,
        "user": user,
        "login_url": login_url,
        "historico_url": url_for("pagina_historico", codigo_usuario=user["codigo_usuario"], _external=True),
    }


def validate_extension_url(url: str):
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, None, None

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if hostname not in ALLOWED_MERCADOLIVRE_HOSTS:
        return False, None, parsed

    return True, PLATFORM_MERCADOLIVRE, parsed


def detect_mercadolivre_product_page(parsed_url) -> bool:
    if not parsed_url:
        return False

    path = parsed_url.path or ""
    if "/p/" in path.lower():
        return True

    if "MLB-" in path.upper() or "/MLB" in path.upper():
        return True

    return False


def build_product_preview(url: str):
    is_valid, platform, parsed = validate_extension_url(url)
    if not is_valid:
        return {
            "is_valid": False,
            "platform": None,
            "is_product_page": False,
            "estimated_cashback_percent": None,
            "estimated_cashback_value": None,
            "message": "Esta página não é compatível.",
            "cta": None,
        }

    is_product_page = detect_mercadolivre_product_page(parsed)
    if not is_product_page:
        return {
            "is_valid": True,
            "platform": platform,
            "is_product_page": False,
            "estimated_cashback_percent": None,
            "estimated_cashback_value": None,
            "message": "Acesse uma página de produto para gerar um link com cashback.",
            "cta": None,
        }

    # Regra provisória de preview visual. Cashback oficial será definido em PR futuro.
    return {
        "is_valid": True,
        "platform": platform,
        "is_product_page": True,
        "estimated_cashback_percent": EXTENSION_ESTIMATED_CASHBACK_PERCENT,
        "estimated_cashback_value": None,
        "message": "Produto com cashback disponível.",
        "cta": "Gerar link com cashback",
    }
