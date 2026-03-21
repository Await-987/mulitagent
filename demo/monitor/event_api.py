import ast
import json
import os
import time
from datetime import datetime
from typing import Dict, Iterable, List
from demo import WORKING_DIRECTORY
from flask import Flask, Response, jsonify, render_template, request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))

RUNS_DIR = WORKING_DIRECTORY

app = Flask(
    __name__,
    template_folder=os.path.join(_HERE, "templates"),
    static_folder=os.path.join(_HERE, "static"),
)


def _safe_parse_value(raw: str):
    text = raw.strip()
    if text == "":
        return ""
    if (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    ):
        try:
            return json.loads(text)
        except Exception:
            pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def _parse_event_file(path: str) -> Dict:
    event: Dict[str, object] = {
        "source_file": os.path.basename(path),
    }
    raw_values: Dict[str, str] = {}
    current_key = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if ": " in line:
                key, value = line.split(": ", 1)
                raw_values[key] = value
                current_key = key
                continue
            if current_key:
                raw_values[current_key] = (
                    raw_values.get(current_key, "") + "\n" + line
                )
    for key, value in raw_values.items():
        if key in ("timestamp", "event_type", "workforce_id", "task_id"):
            event[key] = value
            continue
        event[key] = _safe_parse_value(value)
    return event


def _list_runs() -> List[str]:
    if not os.path.isdir(RUNS_DIR):
        return []
    runs = [
        name
        for name in os.listdir(RUNS_DIR)
        if os.path.isdir(os.path.join(RUNS_DIR, name))
    ]
    runs.sort(reverse=True)
    return runs


def _event_files_for_run(run_id: str) -> List[str]:
    run_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(run_dir):
        return []
    files = [
        os.path.join(run_dir, name)
        for name in os.listdir(run_dir)
        if name.endswith(".txt")
    ]
    files.sort()
    return files


def _read_events(run_id: str) -> List[Dict]:
    events = []
    for path in _event_files_for_run(run_id):
        try:
            events.append(_parse_event_file(path))
        except Exception as exc:
            events.append(
                {
                    "event_type": "parse_error",
                    "error": str(exc),
                    "source_file": os.path.basename(path),
                }
            )
    return events


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/runs")
def api_runs():
    runs = _list_runs()
    return jsonify(
        {
            "runs": runs,
            "latest": runs[0] if runs else None,
        }
    )


@app.route("/api/runs/latest")
def api_runs_latest():
    runs = _list_runs()
    return jsonify(
        {
            "latest": runs[0] if runs else None,
        }
    )


@app.route("/api/events")
def api_events():
    run_id = request.args.get("run")
    if not run_id:
        runs = _list_runs()
        run_id = runs[0] if runs else None
    if not run_id:
        return jsonify({"events": [], "run": None})
    return jsonify({"events": _read_events(run_id), "run": run_id})


def _stream_events(run_id: str) -> Iterable[str]:
    known = set()
    while True:
        files = _event_files_for_run(run_id)
        for path in files:
            if path in known:
                continue
            known.add(path)
            try:
                event = _parse_event_file(path)
            except Exception as exc:
                event = {
                    "event_type": "parse_error",
                    "error": str(exc),
                    "source_file": os.path.basename(path),
                }
            payload = json.dumps(event, ensure_ascii=False)
            yield f"event: workforce\ndata: {payload}\n\n"
        time.sleep(1.0)


@app.route("/api/stream")
def api_stream():
    run_id = request.args.get("run")
    if not run_id:
        runs = _list_runs()
        run_id = runs[0] if runs else None
    if not run_id:
        return jsonify({"error": "no runs found"}), 404
    return Response(
        _stream_events(run_id),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "status": "ok",
            "time": datetime.utcnow().isoformat() + "Z",
            "runs": len(_list_runs()),
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
