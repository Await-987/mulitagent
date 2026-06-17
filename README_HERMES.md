# Hermes Soul Runtime 说明

本文件补充说明 Hermes 在 ORCA/AIOS 中的接入方式。主 README 已覆盖完整启动流程；这里更关注 Hermes Soul 的运行边界、环境融合和排错。

## 接入边界

当前项目只让 **Soul Agent 使用 Hermes**：

```text
User task
  -> Hermes Soul Agent
  -> enriched task
  -> Camel Workforce
  -> Camel App Agents
  -> result
```

Coordinator、Task Agent、Document、Notes、Photos、XiaoHongShu、Xiecheng、Contactors 等执行层 Agent 仍由 Camel/AIOS 管理。Hermes 不是 App Agent，也不是完整替换 Workforce 的执行器。

## 统一环境

Hermes Soul 模式使用一个 Python 3.11 环境。推荐环境名为 `aios-hermes`：

```bash
./scripts/setup_aios_hermes.sh
conda activate aios-hermes
```

该环境同时安装：

- 本项目 Python 依赖
- 本地 `camel-master`
- 本地 Hermes agent 的 `acp` 和 `web` 依赖

Hermes ACP 子进程由 `AIOS_HERMES_PYTHON` 指向同一个 Python 解释器。这样 AIOS、Camel、Hermes client 和 ACP subprocess 不再分属两个虚拟环境。

## Hermes agent 源码位置

默认查找：

```text
$HOME/.hermes/hermes-agent
```

如果 Hermes agent 在其他目录，运行 setup 前设置：

```bash
export AIOS_HERMES_AGENT_ROOT=/path/to/hermes-agent
./scripts/setup_aios_hermes.sh
```

`requirements-unified-py311.txt` 会通过 `${AIOS_HERMES_AGENT_ROOT}` 安装 Hermes agent，因此该变量必须指向包含 `pyproject.toml` 的源码目录。

## 启动 OS View

```bash
./scripts/run_os_view_hermes.sh
```

脚本会读取 `.env`，并设置：

```bash
AIOS_AGENT_RUNTIME=hermes
AIOS_HERMES_PYTHON=<current-python>
AIOS_HERMES_RUNTIME_DIR=<project>/runtime/hermes
```

启动后访问：

```text
http://127.0.0.1:5001
```

## 启动命令行 Demo

```bash
./scripts/run_demo_hermes.sh
```

该入口适合快速观察 Hermes Soul 生成的 enriched task，以及 Camel Workforce 后续执行过程。

## 运行环境检查

```bash
python scripts/hermes_doctor.py
```

重点检查：

- `hermes_agent_root_exists` 应为 `true`
- `python_executable_exists` 应为 `true`
- `current_python_version` 应为 `3.11`
- `acp_importable_in_current_python` 应为 `true`
- `runtime_dir_exists` 首次运行前可以为 `false`

如果看到 `Current Python cannot import ACP`，通常说明没有激活统一的 Python 3.11 环境，或 Hermes agent 没有安装进该环境。

## Soul 工具桥

Hermes Soul 通过 MCP server 访问 AIOS 的 Soul 能力：

```text
mcp_servers/soul_mcp_server.py
```

暴露给 Hermes 的工具包括：

- `soul__get_user_soul`：读取用户画像和经历
- `soul__get_task_status`：读取当前任务状态
- `soul__update_soul_profile`：更新用户画像字段
- `soul__append_experience`：追加经历
- `soul__ask_human`：向用户发起澄清或确认

这些工具让 Hermes 能做任务理解和用户澄清，但不让 Hermes 直接绕过 Workforce 操作所有 App 数据。

## Fallback 策略

`.env` 中的 `AIOS_HERMES_FALLBACK` 控制 Hermes 失败时是否回退到 Camel Soul：

```env
AIOS_HERMES_FALLBACK=on_error
```

可选值：

| 值 | 行为 |
| --- | --- |
| `never` | Hermes 失败就直接报错 |
| `on_error` | Hermes 报错时回退到 Camel Soul |
| `on_empty` | Hermes 输出为空时回退 |
| `always` | 每次都跑 Hermes 和 Camel，主要用于调试 |

严格验证 Hermes 时建议用 `never`。演示时建议保留 `on_error`，避免模型服务短暂异常导致整条 Demo 中断。

## 常见问题

### setup 后是否还要进入 Hermes 自己的 venv？

不需要。setup 的目标就是把 AIOS、Camel 和 Hermes 安装到同一个 Python 3.11 环境。后续只进入 `aios-hermes` 即可。

### 为什么不把所有 App Agent 都切到 Hermes？

Hermes 更像系统级 Soul：适合长期记忆、用户理解和主动澄清。App Agent 需要的是明确工具边界和稳定执行。让所有 App Agent 都变成 Hermes 会显著增加运行成本、状态复杂度和权限风险。

### 运行产物在哪里？

默认在：

```text
runtime/hermes
```

其中会生成 Hermes agent home、`SOUL.md`、`memories/USER.md`、`memories/MEMORY.md`、运行日志和事件 trace。这些都属于本地运行产物，不需要提交。
