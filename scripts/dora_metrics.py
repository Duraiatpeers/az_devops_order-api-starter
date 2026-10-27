"""Module 8: DORA-style delivery metrics from an environment's deployment history.

Uses: GET _apis/distributedtask/environments/{id}/environmentdeploymentrecords (Azure DevOps REST).
--fixture lets you run it offline against a saved JSON response.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone

from aoai import ado


def ts(s):
    """Parse Azure DevOps timestamps such as 2026-10-23T10:00:00.1234567Z (7 fractional digits)."""
    s = re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def metrics(records, days=30):
    now = datetime.now(timezone.utc)
    recs = sorted((r for r in records if r.get("finishTime")), key=lambda r: r["finishTime"])
    recs = [r for r in recs if ts(r["finishTime"]) >= now - timedelta(days=days)]
    total = len(recs)
    failed = [r for r in recs if r.get("result") == "failed"]
    # Failed-deployment recovery time: failed deployment -> next successful one.
    recoveries = []
    for i, r in enumerate(recs):
        if r.get("result") == "failed":
            nxt = next((n for n in recs[i + 1:] if n.get("result") == "succeeded"), None)
            if nxt:
                recoveries.append((ts(nxt["finishTime"]) - ts(r["finishTime"])).total_seconds() / 3600)
    return {
        "window_days": days,
        "deployments": total,
        "deployment_frequency_per_week": round(total / (days / 7), 2),
        "change_failure_rate_pct": round(100 * len(failed) / total, 1) if total else 0.0,
        "median_recovery_hours": round(sorted(recoveries)[len(recoveries) // 2], 2) if recoveries else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--environment", default="production")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--fixture")
    a = ap.parse_args()
    if a.fixture:
        records = json.load(open(a.fixture))["value"]
    else:
        envs = ado("GET", f"distributedtask/environments?name={a.environment}&api-version=7.1")["value"]
        env_id = envs[0]["id"]
        records = ado("GET", f"distributedtask/environments/{env_id}/environmentdeploymentrecords"
                             f"?top=500&api-version=7.1")["value"]
    print(json.dumps(metrics(records, a.days), indent=2))


if __name__ == "__main__":
    main()
