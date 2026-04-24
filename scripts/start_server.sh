#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
DEFAULT_VENV_DIR="$PROJECT_ROOT/venv"
if [[ ! -f "$DEFAULT_VENV_DIR/bin/activate" && -f "$PROJECT_ROOT/.venv/bin/activate" ]]; then
  DEFAULT_VENV_DIR="$PROJECT_ROOT/.venv"
fi
VENV_DIR="${VENV_DIR:-$DEFAULT_VENV_DIR}"
APP_MODULE="${APP_MODULE:-app:app}"
BIND_ADDRESS="${BIND_ADDRESS:-127.0.0.1:5000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERRO] Arquivo .env nao encontrado em $ENV_FILE"
  exit 1
fi

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "[ERRO] Virtualenv nao encontrada em $VENV_DIR"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${APP_ENV:=production}"
: "${SECURE_STORAGE_DIR:=$HOME/.afiliados-mvp}"
: "${LOGS_DIR:=$SECURE_STORAGE_DIR/logs}"

if [[ -z "${SECRET_KEY:-}" ]]; then
  echo "[ERRO] SECRET_KEY ausente no .env"
  exit 1
fi

if [[ -z "${WORKER_API_TOKEN:-}" ]]; then
  echo "[ERRO] WORKER_API_TOKEN ausente no .env"
  exit 1
fi

mkdir -p "$SECURE_STORAGE_DIR" "$LOGS_DIR"

source "$VENV_DIR/bin/activate"

OLD_PIDS="$(lsof -ti tcp:5000 -sTCP:LISTEN || true)"
if [[ -n "$OLD_PIDS" ]]; then
  echo "[INFO] Encerrando Gunicorn antigo na porta 5000..."
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    cmd="$(ps -p "$pid" -o command= || true)"
    if [[ "$cmd" == *gunicorn* ]]; then
      kill -TERM "$pid" || true
    else
      echo "[AVISO] Processo na porta 5000 nao parece Gunicorn: PID=$pid CMD=$cmd"
    fi
  done <<< "$OLD_PIDS"

  sleep 2

  STILL_RUNNING="$(lsof -ti tcp:5000 -sTCP:LISTEN || true)"
  if [[ -n "$STILL_RUNNING" ]]; then
    echo "[AVISO] Ainda havia processo(s) na porta 5000. Forcando encerramento..."
    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      cmd="$(ps -p "$pid" -o command= || true)"
      if [[ "$cmd" == *gunicorn* ]]; then
        kill -KILL "$pid" || true
      fi
    done <<< "$STILL_RUNNING"
  fi
fi

echo "[INFO] Iniciando Gunicorn em $BIND_ADDRESS"
gunicorn "$APP_MODULE" \
  --bind "$BIND_ADDRESS" \
  --workers "$GUNICORN_WORKERS" \
  --timeout "$GUNICORN_TIMEOUT" \
  --pid "$SECURE_STORAGE_DIR/gunicorn.pid" \
  --access-logfile "$LOGS_DIR/gunicorn-access.log" \
  --error-logfile "$LOGS_DIR/gunicorn-error.log" \
  --daemon

echo "[OK] Gunicorn iniciado."
echo "[INFO] PID file: $SECURE_STORAGE_DIR/gunicorn.pid"
echo "[INFO] Logs: $LOGS_DIR/gunicorn-access.log | $LOGS_DIR/gunicorn-error.log"
