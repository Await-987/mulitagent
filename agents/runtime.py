import os

_VALID_RUNTIMES = {"camel", "hermes"}


def get_agent_runtime() -> str:
    runtime = os.environ.get("AIOS_AGENT_RUNTIME", "camel").strip().lower()
    if runtime not in _VALID_RUNTIMES:
        raise ValueError(
            f"Invalid AIOS_AGENT_RUNTIME={runtime!r}. Expected one of: {sorted(_VALID_RUNTIMES)}"
        )
    return runtime


def is_hermes_runtime() -> bool:
    return get_agent_runtime() == "hermes"
