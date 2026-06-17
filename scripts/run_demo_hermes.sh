#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

load_env_file() {
  local env_file="$1"
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *"="* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    export "$key=$value"
  done < "$env_file"
}

PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]] && command -v conda >/dev/null 2>&1; then
  CONDA_BASE="$(conda info --base)"
  # shellcheck disable=SC1091
  source "$CONDA_BASE/etc/profile.d/conda.sh"
  if conda env list | awk '{print $1}' | grep -qx "aios-hermes"; then
    conda activate aios-hermes
    PYTHON_BIN="python"
  fi
fi

if [[ -z "$PYTHON_BIN" && -x ".venv-aios-hermes/bin/python" ]]; then
  PYTHON_BIN=".venv-aios-hermes/bin/python"
fi

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

[[ -f ".env" ]] && load_env_file ".env"

CURRENT_PYTHON="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
CURRENT_PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
if [[ "$CURRENT_PYTHON_VERSION" != "3.11" ]]; then
  echo "[run] Python 3.11 is required for the unified AIOS + Hermes environment." >&2
  echo "[run] Selected Python: $CURRENT_PYTHON ($CURRENT_PYTHON_VERSION)" >&2
  echo "[run] Run ./scripts/setup_aios_hermes.sh, then start again." >&2
  exit 1
fi

export AIOS_AGENT_RUNTIME="hermes"
export AIOS_HERMES_COMPANY="${AIOS_HERMES_COMPANY:-aios}"
export AIOS_HERMES_NAMESPACE="${AIOS_HERMES_NAMESPACE:-$AIOS_HERMES_COMPANY}"
export AIOS_HERMES_EMPLOYEE_ID="${AIOS_HERMES_EMPLOYEE_ID:-main}"
export AIOS_HERMES_HOME="${AIOS_HERMES_HOME:-$HOME/.hermes}"
export AIOS_HERMES_AGENT_ROOT="${AIOS_HERMES_AGENT_ROOT:-$AIOS_HERMES_HOME/hermes-agent}"
# Keep AIOS, Camel, Hermes client code, and the Hermes ACP subprocess on one
# Python environment. The Hermes source tree is installed editable into this env.
export AIOS_HERMES_PYTHON="$CURRENT_PYTHON"
export AIOS_HERMES_RUNTIME_DIR="${AIOS_HERMES_RUNTIME_DIR:-$ROOT_DIR/runtime/hermes}"

echo "[run] AIOS_AGENT_RUNTIME=$AIOS_AGENT_RUNTIME"
echo "[run] Python: $($PYTHON_BIN -V 2>&1) ($CURRENT_PYTHON)"
echo "[run] Hermes Python: $AIOS_HERMES_PYTHON"

exec "$PYTHON_BIN" demo/aios_demo.py
