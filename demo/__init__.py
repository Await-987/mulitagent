import os

_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.join(
    _DEMO_DIR, "working_dir"
)