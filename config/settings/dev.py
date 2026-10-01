"""Configurações de desenvolvimento local (DEBUG=True)."""

from .base import *  # noqa: F401,F403

DEBUG = True

# Em desenvolvimento não há proxy TLS na frente.
SECURE_PROXY_SSL_HEADER = None
SECURE_SSL_REDIRECT = False

# Serviço de estáticos mais simples (sem manifest) em desenvolvimento.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Cookies sem exigência de HTTPS para permitir testes em http://localhost.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
