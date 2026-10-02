#!/usr/bin/env bash
# =====================================================================
# Teste de regressão do scripts/importar_alunos.sh
# ---------------------------------------------------------------------
# Usa um "docker" falso no PATH para capturar os argumentos enviados ao
# contêiner e garante que:
#   - não há argumento vazio (bug do replace do --dry-run);
#   - o --dry-run aparece só na prévia (1 vez);
#   - há duas invocações do import_roster (prévia + aplicar).
#
# Uso: ./scripts/test_importar_alunos.sh
# =====================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
LOG="$TMP/docker.log"
: > "$LOG"

# "docker" falso: registra cada argumento entre [ ] (um por linha).
cat > "$TMP/bin/docker" <<EOF
#!/usr/bin/env bash
case "\$1" in
  inspect) echo "true"; exit 0 ;;
  exec)
    if [ "\${3:-}" = "test" ]; then exit 0; fi
    echo "--- exec ---" >> "$LOG"
    shift 2
    for a in "\$@"; do printf '[%s]\n' "\$a" >> "$LOG"; done
    exit 0 ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$TMP/bin/docker"

# arquivo de entrada fictício (o conteúdo não importa para o teste).
echo "matricula;nome;turma" > "$TMP/alunos.csv"

PATH="$TMP/bin:$PATH" "$ROOT/scripts/importar_alunos.sh" \
    --user teste@exemplo.org --apply --file "$TMP/alunos.csv" >/dev/null

falhou=0
if grep -qx '\[\]' "$LOG"; then
    echo "FALHOU: foi passado um argumento VAZIO."
    falhou=1
fi

dry=$(grep -c '^\[--dry-run\]$' "$LOG" || true)
if [ "$dry" != "1" ]; then
    echo "FALHOU: --dry-run deveria aparecer 1x (prévia), apareceu $dry."
    falhou=1
fi

execs=$(grep -c '^--- exec ---$' "$LOG" || true)
if [ "$execs" != "2" ]; then
    echo "FALHOU: esperava 2 invocações (prévia + aplicar), houve $execs."
    falhou=1
fi

if [ "$falhou" != "0" ]; then
    echo "--- log capturado ---"
    cat "$LOG"
    exit 1
fi

echo "ok: importar_alunos.sh gera os argumentos corretos"
