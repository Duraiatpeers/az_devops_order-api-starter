"""Send N requests to the main URL while traffic is split, count versions and errors.

Fails (exit 1) if the error rate is above the threshold - the 'on: failure' hook then rolls back.
"""
import argparse
import json
import urllib.request
from collections import Counter

ap = argparse.ArgumentParser()
ap.add_argument("base_url")
ap.add_argument("--requests", type=int, default=50)
ap.add_argument("--max-error-pct", type=float, default=2.0)
a = ap.parse_args()

versions, errors = Counter(), 0
for _ in range(a.requests):
    try:
        # no cookie jar: each request is routed independently, so ~canary% should hit the canary slot
        with urllib.request.urlopen(a.base_url.rstrip("/") + "/health", timeout=15) as r:
            versions[json.loads(r.read()).get("version")] += 1
    except Exception:  # noqa: BLE001
        errors += 1
pct = 100 * errors / a.requests
print(f"versions seen: {dict(versions)}; errors: {errors}/{a.requests} ({pct:.1f}%)")
if pct > a.max_error_pct:
    print(f"##vso[task.logissue type=error]Canary error rate {pct:.1f}% > {a.max_error_pct}%")
    raise SystemExit(1)
