#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env")

from hermes_platform import HermesPlatform


def main() -> int:
    platform = HermesPlatform(
        namespace=(
            os.environ.get("AIOS_HERMES_NAMESPACE")
            or os.environ.get("AIOS_HERMES_COMPANY")
            or "aios"
        ),
        hermes_home=os.environ.get("AIOS_HERMES_HOME"),
        hermes_agent_root=os.environ.get("AIOS_HERMES_AGENT_ROOT"),
        python_executable=sys.executable,
        runtime_dir=os.environ.get("AIOS_HERMES_RUNTIME_DIR"),
    )
    report = platform.doctor()
    print(json.dumps(report, ensure_ascii=False, indent=2))

    errors: list[str] = []
    warnings: list[str] = []

    if not report["hermes_agent_root_exists"]:
        errors.append("Hermes agent root does not exist.")
    if not report["python_executable_exists"]:
        errors.append("Hermes Python executable does not exist.")
    if report["current_python_version"] != "3.11":
        errors.append(
            "Current Python is not 3.11. Activate the aios-hermes environment before running AIOS."
        )
    if not report["config_example_exists"]:
        errors.append("Hermes cli-config.yaml.example was not found.")
    if not report["env_example_exists"]:
        errors.append("Hermes .env.example was not found.")
    if not report["skills_sync_py_exists"]:
        warnings.append("Hermes skills_sync.py was not found; role skill sync may fall back to copy.")
    if not report["acp_importable_in_current_python"] and not report["can_bridge_site_packages"]:
        errors.append(
            "Current Python cannot import ACP and cannot bridge Hermes site-packages. "
            "Run with the Python 3.11 aios-hermes environment."
        )
    if not report["runtime_dir_exists"]:
        warnings.append("Hermes runtime_dir does not exist yet; it will be created on first run.")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")
    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nHermes Soul runtime looks usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
