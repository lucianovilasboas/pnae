#!/usr/bin/env bash
# =====================================================================
# IFMG Alimenta — backup do banco (pg_dump dentro do container)
# ---------------------------------------------------------------------
# Uso:
#   ./scripts/backup_db.sh
# Variáveis:
#   DB_CONTAINER (padrão: pnae_db)
#   POSTGRES_USER / POSTGRES_DB
#   BACKUP_DIR (padrão: ./backups)
#   BACKUP_KEEP (padrão: 14) — quantos arquivos manter
# =====================================================================
set -euo pipefail

CONTAINER="${DB_CONTAINER:-pnae_db}"
DB_USER="${POSTGRES_USER:-django_user}"
DB_NAME="${POSTGRES_DB:-django_db}"
DIR="${BACKUP_DIR:-./backups}"
KEEP="${BACKUP_KEEP:-14}"

mkdir -p "$DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$DIR/pnae-$STAMP.sql.gz"

docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner | gzip > "$FILE"
echo "backup: $FILE ($(du -h "$FILE" | cut -f1))"

# Retenção: mantém os N mais recentes.
ls -1t "$DIR"/pnae-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
