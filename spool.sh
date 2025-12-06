#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

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
echo "[orbit] starting main (INGRESS_MODE=${INGRESS_MODE:-kafka})"
exec "${PYTHON}" -m src.main "$@"
