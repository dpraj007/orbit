#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

MODE="agent"
if [[ $# -gt 0 ]]; then
  MODE="$1"
  shift
fi
MODE="${MODE:-agent}"

echo "[orbit] root=${ROOT}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "[orbit] creating virtualenv at ${VENV}"
  python3 -m venv "${VENV}"
  "${PIP}" install --upgrade pip
fi

echo "[orbit] installing dependencies"
"${PIP}" install -r "${ROOT}/requirements.txt"

if [[ -f "${ROOT}/.env" ]]; then
  echo "[orbit] loading .env"
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

export PYTHONPATH="${ROOT}"

if [[ "${MODE}" == "dashboard" ]]; then
  echo "[orbit] starting dashboard only"
  exec "${PYTHON}" -m src.web "$@"
elif [[ "${MODE}" == "both" ]]; then
  echo "[orbit] starting dashboard (background) + agent (foreground)"
  "${PYTHON}" -m src.web >/dev/null 2>&1 &
  DASH_PID=$!
  trap 'kill ${DASH_PID} ${PRUNE_PID:-} 2>/dev/null || true' EXIT
  # Optional auto-pruner to keep chats within first page
  if [[ "${PRUNE_CHATS:-1}" != "0" ]]; then
    echo "[orbit] starting auto-pruner (KEEP=${KEEP:-15})"
    KEEP=${KEEP:-15} RUN_ONCE=0 SERIES_BASE_URL="${SERIES_BASE_URL}" SERIES_API_KEY="${SERIES_API_KEY}" "${ROOT}/scripts/auto_prune_chats.sh" >/dev/null 2>&1 &
    PRUNE_PID=$!
  fi
  sleep 1
  echo "[orbit] dashboard pid=${DASH_PID}"
  echo "[orbit] starting agent (INGRESS_MODE=${INGRESS_MODE:-api})"
  exec "${PYTHON}" -m src.main "$@"
else
  echo "[orbit] starting agent only (INGRESS_MODE=${INGRESS_MODE:-api})"
  if [[ "${PRUNE_CHATS:-1}" != "0" ]]; then
    echo "[orbit] starting auto-pruner (KEEP=${KEEP:-15})"
    KEEP=${KEEP:-15} RUN_ONCE=0 SERIES_BASE_URL="${SERIES_BASE_URL}" SERIES_API_KEY="${SERIES_API_KEY}" "${ROOT}/scripts/auto_prune_chats.sh" >/dev/null 2>&1 &
    PRUNE_PID=$!
    trap 'kill ${PRUNE_PID} 2>/dev/null || true' EXIT
  fi
  exec "${PYTHON}" -m src.main "$@"
fi
