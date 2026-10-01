#!/bin/bash
# =====================================================================
# IFMG Alimenta (PNAE) — ponto de entrada do contêiner
# ---------------------------------------------------------------------
# Variáveis reconhecidas:
#   APP_SERVER=runserver|gunicorn   (padrão: gunicorn)
#   APP_WORKERS=<n>                  (padrão: 3)
#   SKIP_MIGRATE=1                   não roda migrações ao iniciar
# =====================================================================
set -e

APP_SERVER="${APP_SERVER:-gunicorn}"
APP_WORKERS="${APP_WORKERS:-3}"
PORT="${APP_PORT:-8601}"

echo "[entrypoint] APP_SERVER=${APP_SERVER} APP_WORKERS=${APP_WORKERS} PORT=${PORT}"

# 1. Migrações (idempotente).
if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] aplicando migrações..."
    python manage.py migrate --noinput
fi

# 2. Arquivos estáticos (necessário com DEBUG=False; inofensivo em dev).
echo "[entrypoint] coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear >/dev/null

# 3. Servidor.
if [ "$APP_SERVER" = "runserver" ]; then
    echo "[entrypoint] servidor de desenvolvimento em 0.0.0.0:${PORT}"
    exec python manage.py runserver "0.0.0.0:${PORT}"
fi

echo "[entrypoint] gunicorn em 0.0.0.0:${PORT} com ${APP_WORKERS} workers"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "$APP_WORKERS" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
