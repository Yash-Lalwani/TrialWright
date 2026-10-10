import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="preflight-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["LLM_MODE"] = "replay"
