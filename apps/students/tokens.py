"""Token QR e seu hash (ver docs/02-modelo-dados.md §5).

O token é um valor opaco de alta entropia. Guardamos apenas
`HMAC-SHA256(pepper, token)`, que é determinístico e permite busca por
igualdade na leitura, sem expor o token bruto.
"""

import hashlib
import hmac
import secrets

from django.conf import settings

# 20 bytes = 160 bits de entropia, conforme o plano (RN-07).
TOKEN_BYTES = 20


def generate_token() -> str:
    """Gera um token QR opaco, seguro e URL-safe."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Calcula o hash determinístico do token usando o pepper do ambiente."""
    if not token:
        raise ValueError("Token vazio.")
    pepper = (settings.QR_PEPPER or "").encode("utf-8")
    if not pepper:
        raise ValueError("QR_PEPPER não configurado — obrigatório para o hash do QR.")
    return hmac.new(pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()
