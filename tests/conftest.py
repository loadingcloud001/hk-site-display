import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "ingest"))

# app.main reads these at import. Tests never touch a real 「極端情況」 state folder, and the admin switch starts off
# (tests/test_admin_api.py sets its own key).
_STATE = tempfile.mkdtemp(prefix="hk-site-display-test-state-")
atexit.register(shutil.rmtree, _STATE, ignore_errors=True)
os.environ["STATE_DIR"] = _STATE
os.environ.pop("ADMIN_KEY", None)
