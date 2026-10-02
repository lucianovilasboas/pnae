#!/usr/bin/env bash
# =====================================================================
# IFMG Alimenta — importação de estudantes (OVM-1)
# ---------------------------------------------------------------------
# Roda a prévia (dry-run); só grava com --apply.
#
# Uso:
#   ./scripts/importar_alunos.sh --user EMAIL [--apply] \
#       [--file ARQUIVO] [--campus PN] [--campus-name "NOME"] [--academic-year 2026]
#
# Padrões: arquivo alunos-ifmg-pn-matricula-mapeada.xlsx, campus PN.
# =====================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FILE="alunos-ifmg-pn-matricula-mapeada.xlsx"
CAMPUS="PN"
CAMPUS_NAME=""
YEAR="$(date +%Y)"
USER_EMAIL=""
APPLY=0
CONTAINER="pnae_app"

while [ $# -gt 0 ]; do
    case "$1" in
        --file)          FILE="$2"; shift 2 ;;
        --campus)        CAMPUS="$2"; shift 2 ;;
        --campus-name)   CAMPUS_NAME="$2"; shift 2 ;;
        --academic-year) YEAR="$2"; shift 2 ;;
        --user)          USER_EMAIL="$2"; shift 2 ;;
        --apply)         APPLY=1; shift ;;
        -h|--help)
            echo "uso: $0 --user EMAIL [--apply] [--file ARQ] [--campus PN] [--campus-name NOME] [--academic-year 2026]"
            exit 0 ;;
        *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
    esac
done

erro() { echo "ERRO: $*" >&2; exit 1; }

[ -n "$USER_EMAIL" ] || erro "informe --user EMAIL (autor da importação)."
[ -f "$FILE" ] || erro "arquivo não encontrado: $FILE"

docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true \
    || erro "contêiner '$CONTAINER' não está em execução. Rode ./scripts/deploy.sh primeiro."

# Caminho dentro do contêiner (o projeto é montado em /pnae_app).
CONTAINER_FILE="/pnae_app/$FILE"
docker exec "$CONTAINER" test -f "$CONTAINER_FILE" \
    || erro "o arquivo não está visível no contêiner em $CONTAINER_FILE. Copie-o para a raiz do projeto."

ARGS=(python manage.py import_roster "$CONTAINER_FILE"
      --campus "$CAMPUS" --academic-year "$YEAR" --user "$USER_EMAIL" --dry-run)
[ -n "$CAMPUS_NAME" ] && ARGS+=(--campus-name "$CAMPUS_NAME")

echo "-> PRÉVIA (não grava)"
docker exec "$CONTAINER" "${ARGS[@]}"

if [ "$APPLY" != "1" ]; then
    echo
    echo "Prévia concluída. Para gravar, rode de novo com --apply:"
    echo "  $0 --user $USER_EMAIL --apply --campus $CAMPUS --academic-year $YEAR"
    exit 0
fi

ARGS=("${ARGS[@]/--dry-run/}")
echo
echo "-> APLICANDO"
docker exec "$CONTAINER" "${ARGS[@]}"
echo "ok: importação aplicada."
