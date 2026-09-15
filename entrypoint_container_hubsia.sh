#!/bin/sh
set -e

PORT="${PORT:-3000}"
HOST="${HOST:-0.0.0.0}"
DB_PATH="${HUBSIA_DB_PATH:-/data/hubsia.db}"

if [ -z "$HUBSIA_SECRET" ]; then
  echo "ERRO: defina HUBSIA_SECRET no painel (Environment Variables)." >&2
  exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"

echo "Iniciando Hubsia em ${HOST}:${PORT}"
echo "Banco SQLite em: ${DB_PATH}"
echo "Persistência: monte o volume em /data para não perder dados no redeploy"

exec python -m uvicorn aplicacao_fastapi_comparador_agregadores:app \
  --host "$HOST" \
  --port "$PORT"
