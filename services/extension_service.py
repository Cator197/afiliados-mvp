from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

from flask import url_for

from config import MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT

PLATFORM_MERCADOLIVRE = "mercadolivre"
ALLOWED_MERCADOLIVRE_HOSTS = {"mercadolivre.com.br", "www.mercadolivre.com.br"}
MAX_PREVIEW_PRICE = Decimal("1000000")


def get_current_user_from_session(session_obj):
    if not session_obj.get("user_logged_in"):
        return None

    user_id = session_obj.get("user_id")
    codigo_usuario = session_obj.get("codigo_usuario")
    nome = session_obj.get("user_nome")

    if not user_id or not codigo_usuario:
        return None

    return {"id": user_id, "codigo_usuario": codigo_usuario, "nome": nome}


def build_extension_status_response(session_obj):
    user = get_current_user_from_session(session_obj)
    login_url = url_for("pagina_inicial", _external=True)

    if not user:
        return {"logged_in": False, "user": None, "login_url": login_url, "historico_url": None}

    return {
        "logged_in": True,
        "user": user,
        "login_url": login_url,
        "historico_url": url_for("pagina_historico", codigo_usuario=user["codigo_usuario"], _external=True),
    }


def get_default_cashback_percent(platform: str):
    if platform != PLATFORM_MERCADOLIVRE:
        return None
    return float(MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT)


def parse_price_for_preview(value):
    if value is None:
        return None

    if isinstance(value, (int, float, Decimal)):
        try:
            price = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        normalized = raw.replace("R$", "").replace(" ", "").replace(" ", "")
        if "," in normalized and "." in normalized:
            normalized = normalized.replace(".", "").replace(",", ".")
        elif "," in normalized:
            normalized = normalized.replace(",", ".")
        try:
            price = Decimal(normalized)
        except (InvalidOperation, ValueError):
            return None

    if price <= 0 or price > MAX_PREVIEW_PRICE:
        return None
    return float(price)


def calculate_estimated_cashback(price, percent):
    if price is None or percent is None:
        return None
    amount = (Decimal(str(price)) * Decimal(str(percent))) / Decimal("100")
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def format_cashback_label(percent, value):
    if percent is None:
        return None
    if value is not None:
        brl = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"Cashback estimado de até R$ {brl}"

    pct = int(percent) if float(percent).is_integer() else percent
    return f"Cashback estimado de até {pct}%"


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


def build_product_preview(url: str, price=None, title=None, category_hint=None):
    is_valid, platform, parsed = validate_extension_url(url)
    if not is_valid:
        return {
            "is_valid": False,
            "platform": None,
            "is_product_page": False,
            "estimated_cashback_percent": None,
            "estimated_cashback_value": None,
            "estimated_cashback_label": None,
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
            "estimated_cashback_label": None,
            "message": "Acesse uma página de produto para gerar um link com cashback.",
            "cta": None,
        }

    percent = get_default_cashback_percent(platform)
    normalized_price = parse_price_for_preview(price)
    estimated_value = calculate_estimated_cashback(normalized_price, percent)
    return {
        "is_valid": True,
        "platform": platform,
        "is_product_page": True,
        "estimated_cashback_percent": percent,
        "estimated_cashback_value": estimated_value,
        "estimated_cashback_label": format_cashback_label(percent, estimated_value),
        "message": "Produto com cashback disponível.",
        "cta": "Gerar link com cashback",
    }
