"""Wait until <url>/health answers 200 with the expected version (App Service restarts after a deploy).

usage: python scripts/smoke.py https://app-orders-136-dev.azurewebsites.net 1.0.12 [--tries 30]
"""
import argparse
import json
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("base_url")
ap.add_argument("version")
ap.add_argument("--tries", type=int, default=30)
ap.add_argument("--wait", type=int, default=10)
a = ap.parse_args()

for i in range(1, a.tries + 1):
    try:
        with urllib.request.urlopen(a.base_url.rstrip("/") + "/health", timeout=15) as r:
            body = json.loads(r.read())
        if body.get("version") == a.version:
            print(f"OK after {i} attempt(s): {body}")
            raise SystemExit(0)
        print(f"attempt {i}: running version {body.get('version')}, waiting for {a.version}")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - any failure means 'not ready yet'
        print(f"attempt {i}: {exc}")
    time.sleep(a.wait)
print(f"##vso[task.logissue type=error]Smoke test failed: {a.base_url} never reported version {a.version}")
raise SystemExit(1)
