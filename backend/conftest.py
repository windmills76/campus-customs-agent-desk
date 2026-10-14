"""Shared fixtures: every test runs against a throwaway copy, never the working DB or the original."""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so tests can import backend.* and mcp_server.*
ORIGINAL = ROOT / "data" / "campus_customs.db"


@pytest.fixture()
def shop_db(tmp_path, monkeypatch):
    copy = tmp_path / "test_shop.db"
    shutil.copyfile(ORIGINAL, copy)
    monkeypatch.setenv("CAMPUS_DB_PATH", str(copy))
    from mcp_server import shop

    return shop
