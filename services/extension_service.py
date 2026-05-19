from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

from flask import url_for

from config import MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT
from repositories.cashback_rules_repo import list_cashback_rules

PLATFORM_MERCADOLIVRE = "mercadolivre"
ALLOWED_MERCADOLIVRE_HOSTS = {"mercadolivre.com.br", "www.mercadolivre.com.br"}
MAX_PREVIEW_PRICE = Decimal("1000000")
ALLOWED_MATCH_TYPES = {"default", "path_contains", "category_hint_contains"}


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
    platform = normalize_platform(platform)
    if platform != PLATFORM_MERCADOLIVRE:
        return None
    return float(MERCADOLIVRE_DEFAULT_CASHBACK_PERCENT)


def normalize_platform(platform: str | None):
    return (platform or "").strip().lower()


def rule_matches(rule, url: str, category_hint=None):
    match_type = (rule["match_type"] or "").strip().lower()
    match_value = (rule["match_value"] or "").strip().lower()
    if match_type == "default":
        return True
    if match_type == "path_contains":
        return bool(match_value) and match_value in (url or "").strip().lower()
    if match_type == "category_hint_contains":
        return bool(match_value) and match_value in str(category_hint or "").strip().lower()
    return False


def get_applicable_cashback_rule(platform: str, url: str, category_hint=None):
    normalized_platform = normalize_platform(platform)
    rules = list_cashback_rules(platform=normalized_platform)
    specific_rules = [r for r in rules if (r["match_type"] or "").lower() != "default" and r["active"] == 1]
    for rule in specific_rules:
        if rule_matches(rule, url, category_hint):
            return rule
    for rule in rules:
        if (rule["match_type"] or "").lower() == "default" and rule["active"] == 1:
            return rule
    return None


def build_cashback_preview(platform: str, url: str, price=None, category_hint=None):
    rule = get_applicable_cashback_rule(platform, url, category_hint)
    normalized_price = parse_price_for_preview(price)
    if rule:
        percent = float(rule["cashback_percent"])
        rule_meta = {"id": rule["id"], "name": rule["name"], "match_type": rule["match_type"]}
    else:
        percent = get_default_cashback_percent(platform)
        rule_meta = {"id": None, "name": "Fallback padrão", "match_type": "fallback"}
    estimated_value = calculate_estimated_cashback(normalized_price, percent)
    return {
        "estimated_cashback_percent": percent,
        "estimated_cashback_value": estimated_value,
        "estimated_cashback_label": format_cashback_label(percent, estimated_value),
        "cashback_rule": rule_meta,
    }


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

    cashback_preview = build_cashback_preview(platform, url, price=price, category_hint=category_hint)
    return {
        "is_valid": True,
        "platform": platform,
        "is_product_page": True,
        "estimated_cashback_percent": cashback_preview["estimated_cashback_percent"],
        "estimated_cashback_value": cashback_preview["estimated_cashback_value"],
        "estimated_cashback_label": cashback_preview["estimated_cashback_label"],
        "cashback_rule": cashback_preview["cashback_rule"],
        "message": "Produto com cashback disponível.",
        "cta": "Gerar link com cashback",
    }
