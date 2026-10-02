#!/usr/bin/env bash
# =====================================================================
# IFMG Alimenta — restauração de backup em um banco de DESTINO
# ---------------------------------------------------------------------
# Restaura para um banco separado (por padrão django_db_restore) para
# validar o backup sem tocar no banco em uso.
#
# Uso:
#   ./scripts/restore_db.sh backups/pnae-20260101-120000.sql.gz [db_destino]
# =====================================================================
set -euo pipefail

FILE="${1:-}"
TARGET_DB="${2:-django_db_restore}"
CONTAINER="${DB_CONTAINER:-pnae_db}"
DB_USER="${POSTGRES_USER:-django_user}"

if [ -z "$FILE" ]; then
    echo "uso: $0 <arquivo.sql.gz> [db_destino]" >&2
    exit 2
fi
if [ ! -f "$FILE" ]; then
    echo "arquivo não encontrado: $FILE" >&2
    exit 2
fi

docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -q \
    -c "DROP DATABASE IF EXISTS \"$TARGET_DB\";"
docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -q \
    -c "CREATE DATABASE \"$TARGET_DB\";"

gunzip -c "$FILE" | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$TARGET_DB" -q

echo "restaurado em '$TARGET_DB'"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$TARGET_DB" -tAc \
    "SELECT 'students=' || count(*) FROM students_student;"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$TARGET_DB" -tAc \
    "SELECT 'deliveries=' || count(*) FROM distributions_delivery;"
