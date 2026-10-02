"""Configurações de produção (DEBUG=False, atrás de proxy TLS)."""

from .base import *  # noqa: F401,F403

DEBUG = False

# O proxy (Traefik) faz o TLS e repassa X-Forwarded-Proto.
USE_HTTPS_PROXY = config("USE_HTTPS_PROXY", default=True, cast=bool)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if USE_HTTPS_PROXY else None
# Em produção o padrão é redirecionar HTTP -> HTTPS (independe de confiar no proxy).
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)  # noqa: F405

# Cookies exigem HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Cabeçalhos de segurança.
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
