#!/usr/bin/env bash
# =====================================================================
# IFMG Alimenta — deploy de produção (OVM-1 / pnae.lucianovilasboas.com.br)
# ---------------------------------------------------------------------
# Não-interativo: espera o .env já preenchido. Faz pré-checagens, sobe a
# stack (migrate + collectstatic rodam no entrypoint) e espera o healthz.
#
# Uso:
#   ./scripts/deploy.sh [--skip-build] [--no-wait]
#
# Pré-requisitos na máquina:
#   - docker e docker compose;
#   - rede externa "proxy" (Traefik);
#   - .env de produção preenchido (ver .env.example / docs/10-deploy-ovm1.md).
# =====================================================================
set -euo pipefail

SKIP_BUILD=0
WAIT=1
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=1 ;;
        --no-wait)    WAIT=0 ;;
        -h|--help)
            echo "uso: $0 [--skip-build] [--no-wait]"
            exit 0 ;;
        *) echo "argumento desconhecido: $arg" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_FILE="$ROOT/.env"
DOMAIN="pnae.lucianovilasboas.com.br"

erro() { echo "ERRO: $*" >&2; exit 1; }
ok()   { echo "ok: $*"; }

# ---------------------------------------------------------------------
# 1. Pré-checagens
# ---------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || erro "docker não encontrado."
docker compose version >/dev/null 2>&1 || erro "docker compose não encontrado."

docker network inspect proxy >/dev/null 2>&1 \
    || erro "rede externa 'proxy' não existe. Suba o Traefik primeiro."

[ -f "$ENV_FILE" ] || erro ".env não encontrado. Copie .env.example e preencha antes."
ok "docker, compose e rede proxy presentes"

# Valida campos obrigatórios do .env (sem imprimir segredos).
get_env() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- ; }
SENTINEL="troque-por"

for key in SECRET_KEY QR_PEPPER POSTGRES_PASSWORD DATABASE_URL ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS; do
    value="$(get_env "$key" || true)"
    [ -n "$value" ] || erro "$key ausente/vazio no .env."
done

[ "$(get_env DEBUG || true)" = "False" ] || erro "DEBUG deve ser False no .env de produção."
[ "$(get_env USE_HTTPS_PROXY || true)" = "True" ] || erro "USE_HTTPS_PROXY deve ser True no .env."

case "$(get_env SECRET_KEY)" in *"$SENTINEL"*) erro "SECRET_KEY ainda é o valor de exemplo." ;; esac
case "$(get_env QR_PEPPER)"  in *"$SENTINEL"*) erro "QR_PEPPER ainda é o valor de exemplo." ;; esac

case "$(get_env ALLOWED_HOSTS)" in *"$DOMAIN"*) : ;; *) erro "ALLOWED_HOSTS deve conter $DOMAIN." ;; esac
case "$(get_env CSRF_TRUSTED_ORIGINS)" in *"https://$DOMAIN"*) : ;; *) erro "CSRF_TRUSTED_ORIGINS deve conter https://$DOMAIN." ;; esac
ok ".env validado (DEBUG=False, HTTPS, domínio configurado)"

# ---------------------------------------------------------------------
# 2. Subir a stack
# ---------------------------------------------------------------------
if [ "$SKIP_BUILD" = "1" ]; then
    echo "-> docker compose up -d (sem rebuild)"
    docker compose up -d
else
    echo "-> docker compose up -d --build"
    docker compose up -d --build
fi

# ---------------------------------------------------------------------
# 3. Esperar o healthz
# ---------------------------------------------------------------------
URL="https://$DOMAIN/healthz/"
if [ "$WAIT" = "1" ]; then
    echo "-> aguardando $URL"
    for _ in $(seq 1 40); do
        if curl -fsS "$URL" >/dev/null 2>&1; then
            ok "healthz respondeu"
            break
        fi
        sleep 3
    done
    curl -fsS "$URL" >/dev/null 2>&1 || echo "AVISO: healthz ainda não respondeu; verifique os logs."
fi

# ---------------------------------------------------------------------
# 4. Resumo
# ---------------------------------------------------------------------
echo
echo "== containers =="
docker compose ps
echo
echo "Próximos passos:"
echo "  1) criar usuário administrador:"
echo "     docker exec -it pnae_app python manage.py createsuperuser"
echo "  2) importar estudantes:"
echo "     ./scripts/importar_alunos.sh --user SEU_EMAIL [--apply]"
echo "  3) conferir: https://$DOMAIN/"
