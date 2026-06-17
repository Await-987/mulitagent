#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[setup] project: $ROOT_DIR"

export AIOS_HERMES_HOME="${AIOS_HERMES_HOME:-$HOME/.hermes}"
export AIOS_HERMES_AGENT_ROOT="${AIOS_HERMES_AGENT_ROOT:-$AIOS_HERMES_HOME/hermes-agent}"

if [[ ! -f "$AIOS_HERMES_AGENT_ROOT/pyproject.toml" ]]; then
  echo "[setup] Hermes agent source was not found at: $AIOS_HERMES_AGENT_ROOT" >&2
  echo "[setup] Set AIOS_HERMES_AGENT_ROOT to your local hermes-agent checkout." >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  cp example.env .env
  echo "[setup] created .env from example.env"
else
  echo "[setup] .env already exists; leaving it unchanged"
fi

if command -v conda >/dev/null 2>&1; then
  CONDA_BASE="$(conda info --base)"
  # shellcheck disable=SC1091
  source "$CONDA_BASE/etc/profile.d/conda.sh"
  if conda env list | awk '{print $1}' | grep -qx "aios-hermes"; then
    echo "[setup] updating conda env aios-hermes"
    conda env update -n aios-hermes -f environment-aios-hermes.yml --prune
  else
    echo "[setup] creating conda env aios-hermes"
    conda env create -f environment-aios-hermes.yml
  fi
else
  PYTHON_BIN="${PYTHON_BIN:-python3.11}"
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[setup] conda not found and $PYTHON_BIN is unavailable." >&2
    echo "[setup] Install conda or Python 3.11, then rerun this script." >&2
    exit 1
  fi
  echo "[setup] conda not found; creating .venv-aios-hermes with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv-aios-hermes
  .venv-aios-hermes/bin/python -m pip install --upgrade pip
  .venv-aios-hermes/bin/python -m pip install -r requirements-unified-py311.txt
fi

echo
echo "[setup] done"
echo "[setup] edit .env with API keys, then run:"
echo "        ./scripts/run_os_view_hermes.sh"
