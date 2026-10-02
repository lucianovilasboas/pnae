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
CAMPUS_NAME="IFMG - Campus Ponte Nova"
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
            echo "defaults: --campus PN, --campus-name \"IFMG - Campus Ponte Nova\", --academic-year $(date +%Y)"
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

BASE=(python manage.py import_roster "$CONTAINER_FILE"
      --campus "$CAMPUS" --academic-year "$YEAR" --user "$USER_EMAIL")
if [ -n "$CAMPUS_NAME" ]; then
    BASE+=(--campus-name "$CAMPUS_NAME")
fi

echo "-> PRÉVIA (não grava)"
docker exec "$CONTAINER" "${BASE[@]}" --dry-run

if [ "$APPLY" != "1" ]; then
    echo
    echo "Prévia concluída. Para gravar, rode de novo com --apply:"
    echo "  $0 --user $USER_EMAIL --apply --campus $CAMPUS --campus-name \"$CAMPUS_NAME\" --academic-year $YEAR"
    exit 0
fi

echo
echo "-> APLICANDO"
docker exec "$CONTAINER" "${BASE[@]}"
echo "ok: importação aplicada."
