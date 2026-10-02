#!/usr/bin/env bash
# =====================================================================
# IFMG Alimenta — deploy de produção (OVM-1 / pnae.lucianovilasboas.com.br)
# ---------------------------------------------------------------------
# Não-interativo: espera o .env já preenchido. Faz pré-checagens, sobe a
# stack (migrate + collectstatic rodam no entrypoint) e espera o healthz.
#
# Uso:
#   ./scripts/deploy.sh [--skip-build] [--no-wait] [--reset-db] [--yes]
#
#   --reset-db  apaga o volume do banco (pgdata) e sobe do zero.
#               Use quando a senha mudou e o volume é antigo. DESTRUTIVO.
#   --yes       não confirma o --reset-db (para automação).
#
# Pré-requisitos na máquina:
#   - docker e docker compose;
#   - rede externa "proxy" (Traefik);
#   - .env de produção preenchido (ver .env.example / docs/10-deploy-ovm1.md).
# =====================================================================
set -euo pipefail
export LC_ALL=C   # ordenação determinística (host x contêiner)

SKIP_BUILD=0
WAIT=1
RESET_DB=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=1 ;;
        --no-wait)    WAIT=0 ;;
        --reset-db)   RESET_DB=1 ;;
        --yes|-y)     ASSUME_YES=1 ;;
        -h|--help)
            echo "uso: $0 [--skip-build] [--no-wait] [--reset-db] [--yes]"
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

# Assinatura do código (Python + templates) para detectar imagem desatualizada.
code_signature_host() {
    ( cd "$ROOT" && find apps config templates -type f \( -name '*.py' -o -name '*.html' \) \
        -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}
code_signature_container() {
    docker exec pnae_app bash -lc \
        "export LC_ALL=C; cd /pnae_app && find apps config templates -type f \( -name '*.py' -o -name '*.html' \) -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum" \
        2>/dev/null | cut -d' ' -f1
}

# ---------------------------------------------------------------------
# 1. Pré-checagens
# ---------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || erro "docker não encontrado."
docker compose version >/dev/null 2>&1 || erro "docker compose não encontrado."

docker network inspect proxy >/dev/null 2>&1 \
    || erro "rede externa 'proxy' não existe. Suba o Traefik primeiro."

[ -f "$ENV_FILE" ] || erro ".env não encontrado. Copie .env.example e preencha antes."
ok "docker, compose e rede proxy presentes"

get_env() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- ; }
trim() { printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ; }

SENTINEL="troque-por"
for key in SECRET_KEY QR_PEPPER POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS; do
    value="$(get_env "$key" || true)"
    [ -n "$value" ] || erro "$key ausente/vazio no .env."
done

[ "$(trim "$(get_env DEBUG || true)")" = "False" ] || erro "DEBUG deve ser False no .env de produção."
[ "$(trim "$(get_env USE_HTTPS_PROXY || true)")" = "True" ] || erro "USE_HTTPS_PROXY deve ser True no .env."

case "$(get_env SECRET_KEY)" in *"$SENTINEL"*) erro "SECRET_KEY ainda é o valor de exemplo." ;; esac
case "$(get_env QR_PEPPER)"  in *"$SENTINEL"*) erro "QR_PEPPER ainda é o valor de exemplo." ;; esac

# Senha do banco: precisa ser URL-safe (a DATABASE_URL é uma URL) e não a padrão.
DB_PASS="$(get_env POSTGRES_PASSWORD)"
[ "$DB_PASS" = "django_password" ] && erro \
    "POSTGRES_PASSWORD ainda é a padrão ('django_password'). Gere com: python3 -c \"import secrets;print(secrets.token_hex(24))\""
if printf '%s' "$DB_PASS" | grep -qE '[^A-Za-z0-9_-]'; then
    erro "POSTGRES_PASSWORD tem caractere inválido (espaço ou símbolo fora de letras/números/-/_). Gere com: python3 -c \"import secrets;print(secrets.token_hex(24))\""
fi

case "$(get_env ALLOWED_HOSTS)" in *"$DOMAIN"*) : ;; *) erro "ALLOWED_HOSTS deve conter $DOMAIN." ;; esac
case "$(get_env CSRF_TRUSTED_ORIGINS)" in *"https://$DOMAIN"*) : ;; *) erro "CSRF_TRUSTED_ORIGINS deve conter https://$DOMAIN." ;; esac
ok ".env validado (DEBUG=False, HTTPS, domínio e senha de banco ok)"

# Aviso sobre volume de banco pré-existente.
if docker volume ls --format '{{.Name}}' | grep -q 'pgdata$'; then
    echo "AVISO: já existe um volume pgdata (posição do banco). Se você mudou"
    echo "       POSTGRES_PASSWORD depois de um 'up' anterior, o banco ainda tem a"
    echo "       senha antiga e o deploy vai falhar com 'password authentication failed'."
    echo "       Nesse caso, rode com --reset-db (APAGA os dados do banco)."
fi

# ---------------------------------------------------------------------
# 2. (Opcional) Resetar o banco
# ---------------------------------------------------------------------
if [ "$RESET_DB" = "1" ]; then
    echo "AVISO: --reset-db vai APAGAR o volume do banco (pgdata)."
    if [ "$ASSUME_YES" != "1" ]; then
        read -r -p "Confirmar? (digite 'sim') " resposta
        [ "$resposta" = "sim" ] || erro "cancelado pelo usuário."
    fi
    echo "-> docker compose down -v"
    docker compose down -v
fi

# ---------------------------------------------------------------------
# 3. Subir a stack
# ---------------------------------------------------------------------
if [ "$SKIP_BUILD" = "1" ]; then
    echo "-> docker compose up -d (sem rebuild)"
    docker compose up -d
else
    echo "-> docker compose up -d --build"
    docker compose up -d --build
fi

# ---------------------------------------------------------------------
# 4. Esperar o healthz
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
# 5. Checar se o código do contêiner confere com o repositório
# ---------------------------------------------------------------------
if docker inspect -f '{{.State.Running}}' pnae_app 2>/dev/null | grep -q true; then
    HOST_SIG="$(code_signature_host)"
    CONT_SIG="$(code_signature_container)"
    if [ -n "$HOST_SIG" ] && [ "$HOST_SIG" != "$CONT_SIG" ]; then
        echo "AVISO: o código dentro do contêiner NÃO confere com o repositório"
        echo "       (imagem desatualizada — provavelmente faltou o --build)."
        echo "       Rode: docker compose up -d --build   (ou ./scripts/deploy.sh sem --skip-build)"
    else
        ok "código do contêiner confere com o repositório"
    fi
fi

# ---------------------------------------------------------------------
# 6. Resumo
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
