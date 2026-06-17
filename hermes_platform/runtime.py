from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def _expand(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _value(value: str | Path | None) -> str | Path | None:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _first_existing(candidates: list[Path], marker: str | None = None) -> Path:
    for candidate in candidates:
        candidate = candidate.expanduser()
        if marker is None:
            if candidate.exists():
                return candidate.resolve()
        elif (candidate / marker).exists():
            return candidate.resolve()
    return candidates[0].expanduser().resolve()


@dataclass(frozen=True)
class HermesRuntimeConfig:
    """Resolved paths for the local Hermes platform runtime.

    This class is the single place where compatibility with the current
    scattered Hermes install is allowed to live.
    """

    hermes_home: Path
    package_root: Path
    hermes_agent_root: Path
    python_executable: Path
    runtime_dir: Path
    profiles_dir: Path
    instances_dir: Path
    generic_layout: bool = True

    @classmethod
    def discover(
        cls,
        *,
        hermes_home: str | Path | None = None,
        hermes_agent_root: str | Path | None = None,
        python_executable: str | Path | None = None,
        data_dir: str | Path | None = None,
        runtime_dir: str | Path | None = None,
        profiles_dir: str | Path | None = None,
        instances_dir: str | Path | None = None,
        roles_dir: str | Path | None = None,
        companies_dir: str | Path | None = None,
    ) -> "HermesRuntimeConfig":
        package_root = Path(__file__).resolve().parent
        repo_root = package_root.parent

        resolved_home = _expand(
            _value(hermes_home)
            or os.environ.get("HERMES_HOME")
            or os.environ.get("HERMES_DATA_DIR")
            or Path.home() / ".hermes"
        )
        resolved_data = _expand(_value(data_dir) or os.environ.get("HERMES_DATA_DIR") or resolved_home)
        resolved_runtime = _expand(
            _value(runtime_dir)
            or os.environ.get("AIOS_HERMES_RUNTIME_DIR")
            or os.environ.get("HERMES_RUNTIME_DIR")
            or resolved_data / "runtime" / "hermes"
        )

        agent_candidates = []
        if _value(hermes_agent_root):
            agent_candidates.append(_expand(hermes_agent_root))
        env_agent_root = os.environ.get("HERMES_AGENT_ROOT")
        if env_agent_root:
            agent_candidates.append(_expand(env_agent_root))
        agent_candidates.extend(
            [
                repo_root / "hermes-agent",
                resolved_home / "hermes-agent",
            ]
        )
        resolved_agent_root = _first_existing(agent_candidates, "pyproject.toml")

        if _value(python_executable):
            resolved_python = _expand(python_executable)
        else:
            env_python = os.environ.get("HERMES_PYTHON")
            if env_python:
                resolved_python = _expand(env_python)
            else:
                venv_python = resolved_agent_root / "venv" / "bin" / "python"
                resolved_python = venv_python if venv_python.exists() else Path(sys.executable).resolve()

        return cls(
            hermes_home=resolved_home,
            package_root=package_root,
            hermes_agent_root=resolved_agent_root,
            python_executable=resolved_python,
            runtime_dir=resolved_runtime,
            profiles_dir=_expand(
                _value(profiles_dir)
                or _value(roles_dir)
                or os.environ.get("AIOS_HERMES_PROFILES_DIR")
                or os.environ.get("HERMES_PROFILES_DIR")
                or os.environ.get("HERMES_ROLES_DIR")
                or resolved_runtime / "profiles"
            ),
            instances_dir=_expand(
                _value(instances_dir)
                or _value(companies_dir)
                or os.environ.get("AIOS_HERMES_INSTANCES_DIR")
                or os.environ.get("HERMES_INSTANCES_DIR")
                or os.environ.get("AIOS_HERMES_BASE_DIR")
                or os.environ.get("HERMES_COMPANIES_DIR")
                or resolved_runtime / "instances"
            ),
        )

    @property
    def data_dir(self) -> Path:
        return self.runtime_dir

    @property
    def roles_dir(self) -> Path:
        return self.profiles_dir

    @property
    def companies_dir(self) -> Path:
        return self.instances_dir

    @property
    def company_scoped_layout(self) -> bool:
        return self.generic_layout

    @property
    def env_example(self) -> Path:
        return self.hermes_agent_root / ".env.example"

    @property
    def config_example(self) -> Path:
        return self.hermes_agent_root / "cli-config.yaml.example"

    @property
    def bundled_skills(self) -> Path:
        return self.hermes_agent_root / "skills"

    @property
    def skills_sync_py(self) -> Path:
        return self.hermes_agent_root / "tools" / "skills_sync.py"

    @property
    def outer_env(self) -> Path:
        return self.hermes_home / ".env"

    @property
    def outer_config(self) -> Path:
        return self.hermes_home / "config.yaml"

    @property
    def outer_auth(self) -> Path:
        return self.hermes_home / "auth.json"

    @property
    def current_python_version(self) -> str:
        return f"{sys.version_info[0]}.{sys.version_info[1]}"

    def runtime_python_version(self) -> str | None:
        if not self.python_executable.exists():
            return None
        try:
            return subprocess.check_output(
                [
                    str(self.python_executable),
                    "-c",
                    "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
                ],
                text=True,
                timeout=10,
            ).strip()
        except Exception:
            return None

    def can_bridge_site_packages(self) -> bool:
        runtime_version = self.runtime_python_version()
        return runtime_version == self.current_python_version

    def env_for(self, home: str | Path) -> dict[str, str]:
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("HERMES_"):
                env.pop(key, None)
        env["HERMES_HOME"] = str(_expand(home))
        env.pop("PYTHONPATH", None)
        return env

    def ensure_python_site_packages(self) -> None:
        """Make client-side Hermes dependencies importable in this process.

        The long-term answer is a single installed environment. During the
        migration, this keeps the compatibility path isolated in the SDK runtime
        instead of leaking it into AIOS business modules.
        """
        try:
            import acp  # noqa: F401
            return
        except ImportError:
            pass

        if not self.python_executable.exists():
            return
        try:
            output = subprocess.check_output(
                [
                    str(self.python_executable),
                    "-c",
                    (
                        "import site, sys; "
                        "print(f'{sys.version_info[0]}.{sys.version_info[1]}'); "
                        "print(site.getsitepackages()[0])"
                    ),
                ],
                text=True,
                timeout=10,
            ).strip().splitlines()
        except Exception:
            return
        if len(output) < 2:
            return
        runtime_version, site_packages = output[0], output[1]
        if runtime_version != self.current_python_version:
            return
        if site_packages and site_packages not in sys.path:
            sys.path.insert(0, site_packages)


DEFAULT_CONFIG = HermesRuntimeConfig.discover()


def get_default_config() -> HermesRuntimeConfig:
    return DEFAULT_CONFIG
