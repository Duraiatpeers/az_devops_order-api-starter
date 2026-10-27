"""Post-deployment smoke tests. Run with BASE_URL set; skipped otherwise (so CI unit runs ignore them)."""
import json
import os
import urllib.request

import pytest

BASE_URL = os.getenv("BASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="BASE_URL not set")


def get(path):
    with urllib.request.urlopen(BASE_URL.rstrip("/") + path, timeout=15) as r:
        return r.status, json.loads(r.read())


def test_health_reports_expected_version():
    status, body = get("/health")
    assert status == 200 and body["status"] == "ok"
    expected = os.getenv("EXPECTED_VERSION")
    if expected:
        assert body["version"] == expected
