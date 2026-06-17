"""
HermesWorld —— 按 hermes-agent/scripts/install.sh 的逻辑，在
当前 platform 的 roles_dir 下创建一份"干净出厂"的 hermes 角色。

一个角色 = 一个独立的 HERMES_HOME 目录 + 一条 ~/.local/bin/<name> 的启动器。

初始化流程（对齐 install.sh 的 copy_config_templates + 跳过系统级依赖检查）：
  1. 建标准子目录：cron/ sessions/ logs/ pairing/ hooks/ image_cache/
     audio_cache/ memories/ skills/ whatsapp/session/
  2. 从 hermes-agent/.env.example           → <home>/.env
     从 hermes-agent/cli-config.yaml.example → <home>/config.yaml
  3. 写 SOUL.md：
       - 传了 soul=...       → 直接用这份内容
       - 传了 soul_extra=... → 默认模板 + EXTRA 追加
       - 都没传              → install.sh 里那份带注释的默认模板
  4. 用 hermes-agent/tools/skills_sync.py 把 hermes-agent/skills/ 下的 skill
     同步到 <home>/skills/（失败则回退到 cp -r）。
  5. 可选：把外层 hermes_learn/auth.json 复制进去，新角色就不用再登录了。
  6. 可选：把外层 SOUL / memories / sessions / state.db 也拉进来
     （传 inherit_from_outer=...）。

跟 orchestrator 的区别：
  - orchestrator 是程序化 API（ACP 子进程 + 异步事件流）。
  - world_model 是终端入口：角色创建后直接在 shell 里敲 `<name>` 就唤醒。
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..runtime import DEFAULT_CONFIG, HermesRuntimeConfig


# --- 路径常量：仅保留向后兼容读法，运行时以 HermesRuntimeConfig 为准 ----
PROJECT_ROOT = DEFAULT_CONFIG.hermes_home
HERMES_AGENT_ROOT = DEFAULT_CONFIG.hermes_agent_root
VENV_PYTHON = DEFAULT_CONFIG.python_executable
SKILLS_SYNC_PY = DEFAULT_CONFIG.skills_sync_py
ENV_EXAMPLE = DEFAULT_CONFIG.env_example
CONFIG_EXAMPLE = DEFAULT_CONFIG.config_example
BUNDLED_SKILLS = DEFAULT_CONFIG.bundled_skills
OUTER_ENV = DEFAULT_CONFIG.outer_env
WORLD_MODEL_ROOT = Path(__file__).resolve().parent
ROLES_ROOT = DEFAULT_CONFIG.roles_dir

DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"

# 对齐 install.sh 里 `mkdir -p "$HERMES_HOME"/{...}` 那一行
STANDARD_SUBDIRS: tuple[str, ...] = (
    "cron",
    "sessions",
    "logs",
    "pairing",
    "hooks",
    "image_cache",
    "audio_cache",
    "memories",
    "skills",
    "whatsapp/session",
)

# install.sh 里 SOUL_EOF 那段默认模板，原文保留
DEFAULT_SOUL_TEMPLATE = """# Hermes Agent Persona

<!--
This file defines the agent's personality and tone.
The agent will embody whatever you write here.
Edit this to customize how Hermes communicates with you.

Examples:
  - "You are a warm, playful assistant who uses kaomoji occasionally."
  - "You are a concise technical expert. No fluff, just facts."
  - "You speak like a friendly coworker who happens to know everything."

This file is loaded fresh each message -- no restart needed.
Delete the contents (or this file) to use the default personality.
-->
"""

# 角色名：字母/数字/下划线/短横线；必须以字母或下划线开头
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InitReport:
    """create() 做了什么的统计，方便示例脚本打印。"""
    subdirs: list[str]
    templated: list[str]   # 哪些模板文件被写入
    skills_synced: bool
    skills_error: str | None
    inherited: list[str]   # 从外层拉过来的条目
    skipped: list[str]     # 跳过的条目（含原因）


class HermesWorld:
    """一个独立的 hermes 角色 = 一份 HERMES_HOME + 一条终端启动器。

    典型用法::

        # 创建一个干净的团队负责人
        hw = HermesWorld.create("team_leader", soul_extra="你现在的身份是团队负责人...")
        # 之后在任意终端：
        #   team_leader            ← 交互式进入会话
        # 或 Python 里：
        #   HermesWorld.load("team_leader").wake()
    """

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------
    def __init__(
        self,
        name: str,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
    ):
        self._validate_name(name)
        self.config = config or DEFAULT_CONFIG
        self.name = name
        self.base_dir = Path(base_dir).resolve() if base_dir else self.config.roles_dir.resolve()
        self.home = (self.base_dir / name).resolve()

        # 安全：必须落在 base_dir 下。
        if not str(self.home).startswith(str(self.base_dir) + os.sep):
            raise RuntimeError(f"拒绝：{self.home} 不在 {self.base_dir} 下")
        # 绝不允许 home 等于系统 HERMES_HOME 本身（$HOME/.hermes），以免
        # 误写穿到别的 hermes 实例。但允许 home 嵌套在 HERMES_HOME 下面。
        _sys_hermes = self.config.hermes_home.resolve()
        if self.home == _sys_hermes:
            raise RuntimeError(f"拒绝：home 正是系统 HERMES_HOME：{_sys_hermes}")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name or not _NAME_RE.match(name):
            raise ValueError(
                f"非法角色名 {name!r}：只允许字母/数字/下划线/短横线，且以字母或下划线开头"
            )
        if name in {"hermes", "python", "python3", "bash", "sh", "claude"}:
            raise ValueError(f"角色名 {name!r} 会跟系统命令冲突，换一个")

    # ------------------------------------------------------------------
    # 工厂：create / load / create_or_load / list
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        name: str,
        *,
        # —— 人设 ——
        soul: str | None = None,
        soul_extra: str | None = None,
        # —— 跟 install.sh 对齐的可选项 ——
        include_skills: bool = True,
        # —— 便利项：默认把外层已经配好的 config 和凭证拉过来 ——
        # config: 软链到外层那份能跑的 config.yaml（相对路径 symlink，整个
        # world_model/ 被搬运时也不会断）。外层 `hermes config edit` 一改，
        # 所有角色立刻跟着变。False 退回 cli-config.yaml.example 模板。
        # auth:  直接复制一份，不软链（token 旋转不频繁，解耦也方便 revoke）。
        inherit_config: bool = True,
        inherit_auth: bool = True,
        # —— 高级：可选地再把外层一些东西拉进来（e.g. 老会话） ——
        inherit_from_outer: Iterable[str] = (),
        # —— 运行参数 ——
        overwrite: bool = False,
        install_launcher: bool = True,
        bin_dir: Path | None = None,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
    ) -> "HermesWorld":
        """按 install.sh 的方式初始化一个干净的 hermes 角色。

        参数
        ----
        name:               角色名（同时是终端命令名）。
        soul:               完整的 SOUL.md 内容（优先级最高，直接覆盖默认模板）。
        soul_extra:         在默认 SOUL.md 模板末尾追加一段。
        include_skills:     是否把 hermes-agent/skills/ 同步进来（默认 True）。
        inherit_auth:       是否把外层 hermes_learn/auth.json 复制进来（默认 True）。
        inherit_from_outer: 额外要从外层 hermes_learn/ 拉进来的条目名，例如
                            ("SOUL.md", "memories", "sessions", "state.db")。
                            默认空 —— 角色是纯干净出厂状态。
        overwrite:          目标 home 已存在时是否先清空再重建。
        install_launcher:   是否写 ~/.local/bin/<name> 启动器（默认 True）。
        bin_dir:            启动器写入位置，默认 ~/.local/bin。
        """
        cfg = config or DEFAULT_CONFIG
        hw = cls(name, base_dir=base_dir, config=cfg)

        if hw.home.exists():
            if not overwrite:
                raise FileExistsError(
                    f"角色已存在：{hw.home}（传 overwrite=True 可重建）"
                )
            shutil.rmtree(hw.home)

        # ---- Step 1：标准子目录骨架 ----
        hw.home.mkdir(parents=True, exist_ok=False)
        subdirs_made: list[str] = []
        for sub in STANDARD_SUBDIRS:
            p = hw.home / sub
            p.mkdir(parents=True, exist_ok=True)
            subdirs_made.append(sub)

        templated: list[str] = []
        skipped: list[str] = []

        # ---- Step 2：优先继承外层 .env；否则再用 hermes-agent 的 example 模板 ----
        if cfg.outer_env.exists():
            shutil.copy2(cfg.outer_env, hw.home / ".env")
            templated.append(".env (copy from outer)")
        elif cfg.env_example.exists():
            shutil.copy2(cfg.env_example, hw.home / ".env")
            templated.append(".env (from .example)")
        else:
            (hw.home / ".env").touch()
            templated.append(".env (empty)")

        outer_config = cfg.outer_config
        dst_config = hw.home / "config.yaml"
        if inherit_config and outer_config.exists():
            # 软链（相对路径）到外层 config.yaml，这样外层改了配置，
            # 所有角色立刻跟着变；整个 world_model/ 被整体搬到别的机器上
            # （比如 ~/.hermes/world_model/）时相对 symlink 也能正确解析。
            rel = os.path.relpath(outer_config, start=dst_config.parent)
            try:
                os.symlink(rel, dst_config)
                templated.append(f"config.yaml (symlink → {rel})")
            except (OSError, NotImplementedError) as e:
                shutil.copy2(outer_config, dst_config)
                templated.append(f"config.yaml (copy from outer — symlink 失败: {e})")
        elif cfg.config_example.exists():
            shutil.copy2(cfg.config_example, dst_config)
            templated.append("config.yaml (from .example)")
        else:
            skipped.append("config.yaml (模板和外层都不存在)")

        # ---- Step 3：SOUL.md ----
        soul_path = hw.home / "SOUL.md"
        if soul is not None:
            content = soul if soul.endswith("\n") else soul + "\n"
        elif soul_extra:
            content = DEFAULT_SOUL_TEMPLATE.rstrip() + "\n\n[EXTRA]\n" + soul_extra.strip() + "\n"
        else:
            content = DEFAULT_SOUL_TEMPLATE
        soul_path.write_text(content, encoding="utf-8")
        templated.append("SOUL.md")

        # ---- Step 4：skills 同步 ----
        skills_synced = False
        skills_error: str | None = None
        if include_skills:
            skills_synced, skills_error = hw._seed_skills()
        else:
            skipped.append("skills (include_skills=False)")

        # ---- Step 5+：可选的外层继承 ----
        inherited: list[str] = []
        if inherit_auth:
            src = cfg.outer_auth
            if src.exists():
                shutil.copy2(src, hw.home / "auth.json")
                inherited.append("auth.json")
            else:
                skipped.append("auth.json (外层无)")

        if inherit_from_outer:
            got, gone = hw._copy_from_outer(inherit_from_outer)
            inherited.extend(got)
            skipped.extend(gone)

        report = InitReport(
            subdirs=subdirs_made,
            templated=templated,
            skills_synced=skills_synced,
            skills_error=skills_error,
            inherited=inherited,
            skipped=skipped,
        )
        hw._last_init_report = report  # type: ignore[attr-defined]

        logger.info("created role %s at %s", name, hw.home)

        if install_launcher:
            launcher_path = hw.install_launcher(bin_dir=bin_dir, force=overwrite)
            logger.info("installed launcher: %s", launcher_path)

        return hw

    @classmethod
    def load(
        cls,
        name: str,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
    ) -> "HermesWorld":
        hw = cls(name, base_dir=base_dir, config=config)
        if not hw.home.exists():
            raise FileNotFoundError(f"角色不存在：{hw.home}")
        return hw

    @classmethod
    def create_or_load(cls, name: str, **kwargs) -> "HermesWorld":
        base_dir = kwargs.get("base_dir")
        config = kwargs.get("config")
        probe = cls(name, base_dir=base_dir, config=config)
        if probe.home.exists():
            return cls.load(name, base_dir=base_dir, config=config)
        return cls.create(name, **kwargs)

    @classmethod
    def list_roles(
        cls,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
    ) -> list[str]:
        cfg = config or DEFAULT_CONFIG
        root = Path(base_dir).resolve() if base_dir else cfg.roles_dir.resolve()
        if not root.exists():
            return []
        return [
            p.name for p in sorted(root.iterdir())
            if p.is_dir() and (p / "SOUL.md").exists()
        ]

    @classmethod
    def list_profiles(
        cls,
        *,
        base_dir: Path | None = None,
        config: HermesRuntimeConfig | None = None,
    ) -> list[str]:
        return cls.list_roles(base_dir=base_dir, config=config)

    # ------------------------------------------------------------------
    # 内部：skills 同步 + 外层继承
    # ------------------------------------------------------------------
    def _seed_skills(self) -> tuple[bool, str | None]:
        """先跑 tools/skills_sync.py；失败就回退到 cp -r。"""
        if self.config.skills_sync_py.exists() and self.config.python_executable.exists():
            env = self._build_env()
            try:
                r = subprocess.run(
                    [str(self.config.python_executable), str(self.config.skills_sync_py)],
                    env=env, cwd=str(self.config.hermes_agent_root),
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    return True, None
                err = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["exit=%d" % r.returncode]
                fallback_err = err[0]
            except Exception as e:  # noqa: BLE001
                fallback_err = f"{type(e).__name__}: {e}"
        else:
            fallback_err = "skills_sync.py 或 venv python 不存在"

        # 回退：直接复制
        if self.config.bundled_skills.exists():
            try:
                shutil.copytree(
                    self.config.bundled_skills, self.home / "skills",
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
                return True, None
            except Exception as e:  # noqa: BLE001
                return False, f"skills_sync 失败 ({fallback_err})；cp -r 也失败：{e}"
        return False, f"skills_sync 失败 ({fallback_err})；hermes-agent/skills/ 不存在"

    def _copy_from_outer(self, items: Iterable[str]) -> tuple[list[str], list[str]]:
        """从 hermes_learn 根目录拉条目进来（给 inherit_from_outer 用）。"""
        ok: list[str] = []
        fail: list[str] = []
        for item in items:
            src = self.config.hermes_home / item
            dst = self.home / item
            if not src.exists():
                fail.append(f"{item} (外层不存在)")
                continue
            try:
                if src.is_dir():
                    shutil.copytree(
                        src, dst,
                        dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.lock", "__pycache__"),
                    )
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                ok.append(item)
            except Exception as e:  # noqa: BLE001
                fail.append(f"{item} (复制失败: {e})")
        return ok, fail

    # ------------------------------------------------------------------
    # 唤醒
    # ------------------------------------------------------------------
    def wake(self, *args: str, check: bool = False) -> int:
        """在当前终端交互式唤醒这个角色。返回子进程退出码。

        等价于在终端敲 `<name> <args...>`。
        """
        if not self.config.python_executable.exists():
            raise RuntimeError(f"找不到 Hermes Python：{self.config.python_executable}")

        env = self._build_env()
        cmd = [str(self.config.python_executable), "-m", "hermes_cli.main", *args]
        rc = subprocess.call(cmd, env=env, cwd=str(self.home))
        if check and rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
        return rc

    def _build_env(self) -> dict[str, str]:
        return self.config.env_for(self.home)

    # ------------------------------------------------------------------
    # 启动器：~/.local/bin/<name>
    # ------------------------------------------------------------------
    def launcher_path(self, bin_dir: Path | None = None) -> Path:
        bd = Path(bin_dir).expanduser().resolve() if bin_dir else DEFAULT_BIN_DIR.resolve()
        return bd / self.name

    def install_launcher(self, *, bin_dir: Path | None = None, force: bool = False) -> Path:
        path = self.launcher_path(bin_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and not force:
            existing = path.read_text(encoding="utf-8", errors="replace")
            if "# world_model:auto-launcher" not in existing:
                raise FileExistsError(
                    f"{path} 已存在且不是本库生成的启动器；传 force=True 才会覆盖"
                )

        path.write_text(self._render_launcher_script(), encoding="utf-8")
        path.chmod(0o755)

        path_env = os.environ.get("PATH", "")
        if str(path.parent) not in path_env.split(os.pathsep):
            logger.warning(
                "注意：%s 不在 $PATH 里，直接敲 `%s` 可能找不到命令。"
                "把它加到 shell rc 里：export PATH=\"%s:$PATH\"",
                path.parent, self.name, path.parent,
            )
        return path

    def uninstall_launcher(self, *, bin_dir: Path | None = None) -> bool:
        path = self.launcher_path(bin_dir)
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8", errors="replace")
        if "# world_model:auto-launcher" not in content:
            raise RuntimeError(f"{path} 不是本库生成的启动器，不删")
        path.unlink()
        return True

    def _render_launcher_script(self) -> str:
        import shlex
        home_q = shlex.quote(str(self.home))
        py_q = shlex.quote(str(self.config.python_executable))
        return (
            "#!/usr/bin/env bash\n"
            "# world_model:auto-launcher\n"
            f"# role={self.name}\n"
            f"# home={self.home}\n"
            "set -e\n"
            "# 去掉继承自父 shell 的 HERMES_* 污染\n"
            "while IFS='=' read -r __k _; do\n"
            "  case \"$__k\" in HERMES_*) unset \"$__k\";; esac\n"
            "done < <(env)\n"
            f"export HERMES_HOME={home_q}\n"
            f"cd {home_q}\n"
            f"exec {py_q} -m hermes_cli.main \"$@\"\n"
        )

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------
    def remove(self, *, remove_home: bool = True, remove_launcher: bool = True,
               bin_dir: Path | None = None) -> None:
        if remove_launcher:
            try:
                self.uninstall_launcher(bin_dir=bin_dir)
            except FileNotFoundError:
                pass
        if remove_home and self.home.exists():
            shutil.rmtree(self.home)

    # ------------------------------------------------------------------
    # 杂项
    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"HermesWorld(name={self.name!r}, home={self.home})"
