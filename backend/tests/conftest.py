"""Test configuration: use a throw-away SQLite DB and upload folder."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="internai-test-")
os.environ.setdefault("INTERNAI_DB_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("INTERNAI_UPLOAD_DIR", f"{_tmp}/uploads")
