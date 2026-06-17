from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

from .runtime import HermesRuntimeConfig


class HermesPlatform:
    """Small facade for callers that should not know Hermes' directory layout."""

    def __init__(
        self,
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
        namespace: str | None = None,
        company: str | None = None,
    ) -> None:
        self.namespace = (
            namespace
            or company
            or os.environ.get("AIOS_HERMES_NAMESPACE")
            or os.environ.get("AIOS_HERMES_COMPANY")
            or "default"
        )
        self.config = HermesRuntimeConfig.discover(
            hermes_home=hermes_home,
            hermes_agent_root=hermes_agent_root,
            python_executable=python_executable,
            data_dir=data_dir,
            runtime_dir=runtime_dir,
            profiles_dir=profiles_dir,
            instances_dir=instances_dir,
            roles_dir=roles_dir,
            companies_dir=companies_dir,
        )

    @property
    def company(self) -> str:
        return self.namespace

    @classmethod
    def for_company(cls, company: str, **kwargs) -> "HermesPlatform":
        return cls(company=company, **kwargs)

    @classmethod
    def for_namespace(cls, namespace: str, **kwargs) -> "HermesPlatform":
        return cls(namespace=namespace, **kwargs)

    def world(self, name: str):
        from .world import HermesWorld

        return HermesWorld(name, config=self.config)

    def profile(self, name: str):
        return self.world(name)

    def create_world(self, name: str, **kwargs):
        from .world import HermesWorld

        kwargs.setdefault("config", self.config)
        return HermesWorld.create(name, **kwargs)

    def create_profile(self, name: str, **kwargs):
        return self.create_world(name, **kwargs)

    def load_world(self, name: str, **kwargs):
        from .world import HermesWorld

        kwargs.setdefault("config", self.config)
        return HermesWorld.load(name, **kwargs)

    def load_profile(self, name: str, **kwargs):
        return self.load_world(name, **kwargs)

    def create_or_load_agent(self, *args, **kwargs):
        from .orchestrator import HermesAgent

        kwargs.setdefault("config", self.config)
        kwargs.setdefault("base_dir", self.config.instances_dir)
        kwargs.setdefault("company", self.namespace)
        if "profile" in kwargs:
            kwargs.setdefault("role", kwargs.pop("profile"))
        if "instance_id" in kwargs:
            kwargs.setdefault("employee_id", kwargs.pop("instance_id"))
        return HermesAgent.create_or_load(*args, **kwargs)

    def agent_manager(self, **kwargs):
        from .orchestrator import AgentManager

        kwargs.setdefault("config", self.config)
        kwargs.setdefault("base_dir", self.config.instances_dir)
        kwargs.setdefault("namespace", self.namespace)
        return AgentManager(**kwargs)

    def doctor(self) -> dict[str, Any]:
        """Return a lightweight runtime health report for callers and tests."""
        runtime_python_version = self.config.runtime_python_version()
        current_python_version = self.config.current_python_version
        acp_importable = importlib.util.find_spec("acp") is not None
        can_bridge = self.config.can_bridge_site_packages()

        return {
            "hermes_home": str(self.config.hermes_home),
            "hermes_home_exists": self.config.hermes_home.exists(),
            "hermes_agent_root": str(self.config.hermes_agent_root),
            "hermes_agent_root_exists": self.config.hermes_agent_root.exists(),
            "python_executable": str(self.config.python_executable),
            "python_executable_exists": self.config.python_executable.exists(),
            "current_python_version": current_python_version,
            "runtime_python_version": runtime_python_version,
            "python_versions_match": runtime_python_version == current_python_version,
            "can_bridge_site_packages": can_bridge,
            "acp_importable_in_current_python": acp_importable,
            "runtime_dir": str(self.config.runtime_dir),
            "runtime_dir_exists": self.config.runtime_dir.exists(),
            "profiles_dir": str(self.config.profiles_dir),
            "profiles_dir_exists": self.config.profiles_dir.exists(),
            "instances_dir": str(self.config.instances_dir),
            "instances_dir_exists": self.config.instances_dir.exists(),
            "roles_dir": str(self.config.profiles_dir),
            "roles_dir_exists": self.config.profiles_dir.exists(),
            "companies_dir": str(self.config.instances_dir),
            "companies_dir_exists": self.config.instances_dir.exists(),
            "skills_sync_py_exists": self.config.skills_sync_py.exists(),
            "bundled_skills_exists": self.config.bundled_skills.exists(),
            "env_example_exists": self.config.env_example.exists(),
            "config_example_exists": self.config.config_example.exists(),
            "namespace": self.namespace,
            "company": self.namespace,
            "generic_layout": self.config.generic_layout,
            "company_scoped_layout": self.config.generic_layout,
            "employees_dir": str(self.config.instances_dir),
            "employees_dir_exists": self.config.instances_dir.exists(),
        }
