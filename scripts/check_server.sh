#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
SERVER_URL="${SERVER_URL:-http://127.0.0.1:5000/}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERRO] Arquivo .env nao encontrado em $ENV_FILE"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [[ -z "${SECRET_KEY:-}" ]]; then
  echo "[ERRO] SECRET_KEY ausente no .env"
  exit 1
fi

if [[ -z "${WORKER_API_TOKEN:-}" ]]; then
  echo "[ERRO] WORKER_API_TOKEN ausente no .env"
  exit 1
fi

echo "[OK] Variaveis de ambiente carregadas."

if ! lsof -iTCP:5000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRO] Nenhum processo ouvindo em 127.0.0.1:5000"
  exit 1
fi

echo "[OK] Porta 5000 ativa."

HTTP_CODE="$(curl -sS -o /tmp/afiliados-root.html -w '%{http_code}' "$SERVER_URL")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[ERRO] $SERVER_URL retornou HTTP $HTTP_CODE"
  exit 1
fi

echo "[OK] $SERVER_URL retornou 200."
echo "[INFO] HTML salvo temporariamente em /tmp/afiliados-root.html"
