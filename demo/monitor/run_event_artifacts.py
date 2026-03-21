import os
import sys
import threading
import json
import logging
from datetime import datetime
from loguru import logger as loguru_logger


class RunEventArtifacts:
    def __init__(self, working_dir: str):
        self._working_dir = working_dir
        self.run_output_dir = None

    @staticmethod
    def ensure_camel_src_on_path() -> None:
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        )
        camel_src = os.path.join(repo_root, "camel-master")
        if camel_src not in sys.path:
            sys.path.insert(0, camel_src)

    def prepare_run_output_dir(self) -> str:
        run_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        run_output_dir = os.path.join(self._working_dir, run_stamp)
        os.makedirs(run_output_dir, exist_ok=True)
        self.run_output_dir = run_output_dir
        return run_output_dir

    def attach_event_file_writer(self, metrics_logger) -> None:
        if not self.run_output_dir:
            raise RuntimeError("run_output_dir is not prepared yet.")

        os.makedirs(self.run_output_dir, exist_ok=True)
        lock = threading.Lock()
        counter = {"n": 0}
        original_log_event = metrics_logger._log_event

        def _write_event_file(event: dict) -> None:
            with lock:
                counter["n"] += 1
                idx = counter["n"]

            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
            filename = f"workforce_event_{ts}_{idx:05d}.txt"
            path = os.path.join(self.run_output_dir, filename)

            worker_id = event.get("worker_id")
            worker_role = None
            if worker_id:
                info = metrics_logger._worker_information.get(worker_id, {})
                worker_role = info.get("role")
                if isinstance(worker_role, str):
                    worker_role = worker_role.split(":", 1)[0].strip()

            lines = [
                f"timestamp: {event.get('timestamp', '')}",
                f"workforce_id: {event.get('workforce_id', '')}",
                f"event_type: {event.get('event_type', '')}",
            ]

            if worker_id:
                lines.append(f"worker_id: {worker_id}")
            if worker_role:
                lines.append(f"worker_role: {worker_role}")

            for key, value in event.items():
                if key in ("timestamp", "workforce_id", "event_type"):
                    continue

                if isinstance(value, (dict, list)):
                    lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                elif isinstance(value, str) and "\n" in value:
                    lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                else:
                    lines.append(f"{key}: {value}")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        def patched_log_event(event_type: str, **kwargs):
            original_log_event(event_type, **kwargs)

            try:
                event = metrics_logger.log_entries[-1]
            except Exception:
                event = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "workforce_id": metrics_logger.workforce_id,
                    "event_type": event_type,
                    **kwargs,
                }

            _write_event_file(event)

        metrics_logger._log_event = patched_log_event

    def attach_agent_message_event_bridge(self, metrics_logger) -> None:
        class _AgentMessageHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    message = record.getMessage()
                except Exception:
                    return

                if "Agent Message:" not in message:
                    return

                metrics_logger._log_event(
                    "agent_message",
                    logger_name=record.name,
                    level=record.levelname,
                    message=message,
                    file=record.pathname,
                    line=record.lineno,
                    function=record.funcName,
                    time=datetime.utcfromtimestamp(record.created).isoformat() + "Z",
                )

        camel_logger = logging.getLogger("camel")
        for handler in camel_logger.handlers:
            if isinstance(handler, _AgentMessageHandler):
                return

        handler = _AgentMessageHandler()
        handler.setLevel(logging.INFO)
        camel_logger.addHandler(handler)

    def attach_loguru_tool_event_bridge(self, metrics_logger) -> None:
        def _sink(message):
            record = message.record
            name = record.get("name", "")
            if not name.startswith("tools."):
                return
            metrics_logger._log_event(
                "tool_log",
                logger_name=name,
                level=record.get("level", {}).get("name"),
                message=record.get("message"),
                file=record.get("file", {}).get("name"),
                line=record.get("line"),
                function=record.get("function"),
                time=record.get("time").isoformat() if record.get("time") else "",
            )

        loguru_logger.add(_sink, level="INFO")

    def log_original_task(self, metrics_logger, ori_task: str) -> None:
        metrics_logger._log_event(
            "ori_task",
            description=ori_task,
        )


RunEventArtifacts.ensure_camel_src_on_path()
