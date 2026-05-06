from urllib.parse import urlparse

from config import DOMINIOS_MERCADOLIVRE, DOMINIOS_SHOPEE

PLATFORM_MERCADOLIVRE = "mercadolivre"
PLATFORM_SHOPEE = "shopee"
ACTIVE_PLATFORMS = {PLATFORM_MERCADOLIVRE}
LEGACY_PLATFORMS = {PLATFORM_SHOPEE}
SUPPORTED_PLATFORMS = ACTIVE_PLATFORMS | LEGACY_PLATFORMS


PLATFORM_DOMAIN_MAP = {
    PLATFORM_MERCADOLIVRE: DOMINIOS_MERCADOLIVRE,
    PLATFORM_SHOPEE: DOMINIOS_SHOPEE,
}


def detect_platform_from_url(url: str) -> str | None:
    parsed = urlparse(url)

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return None

    for platform, domains in PLATFORM_DOMAIN_MAP.items():
        for domain in domains:
            domain = domain.lower()
            if hostname == domain or hostname.endswith(f".{domain}"):
                return platform

    return None
