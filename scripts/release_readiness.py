"""Module 8: release-readiness scorecard with an AI risk summary and draft release notes.

Deterministic hard gates decide GO / NO-GO. The AI section is advisory and can never turn a
NO-GO into a GO. The result is attached to the run summary and exposed as an output variable
so the production environment's human approver sees it before approving.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

from aoai import BANNER, ado, ask, upload_summary

WI_REF = re.compile(r"#(\d+)")
SRC_EXT = (".py",)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def junit(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    tot = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    tot["failed"] = tot.pop("failures") + tot.pop("errors")
    return tot


def coverage(path):
    return round(float(ET.parse(path).getroot().get("line-rate")) * 100, 1)


def change_set(since):
    """Commits since the last release. Each commit: (short sha, subject, full message).
    Squash merges from Azure Repos carry the IDs in the body ("Related work items: #63")."""
    rng = f"{since}..HEAD" if since else "HEAD~20..HEAD"
    raw = git("log", "--format=%h%x1f%s%x1f%B%x1e", rng)
    commits = [tuple(c.strip("\n").split("\x1f", 2)) for c in raw.split("\x1e") if c.strip()]
    files = Counter()
    added = deleted = 0
    for line in git("log", "--numstat", "--format=", rng).splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            a, d, f = parts
            files[f] += 1
            added += int(a) if a.isdigit() else 0
            deleted += int(d) if d.isdigit() else 0
    return commits, files, added, deleted


def hotspots(changed, days=90, min_churn=3, top=5):
    """Files in this release that changed at least min_churn times in the last `days` days."""
    names = git("log", f"--since={days}.days", "--name-only", "--format=").splitlines()
    churn = Counter(n for n in names if n)
    return sorted(((f, churn[f]) for f in changed if churn[f] >= min_churn), key=lambda x: -x[1])[:top]


def parse_ts(value):
    """Azure DevOps timestamps can carry 7 fractional digits; Python accepts 6."""
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00"))


def anomalies(top=20):
    """Compare this pipeline's recent history: duration outliers and failure rate (needs a token)."""
    if not (os.getenv("SYSTEM_ACCESSTOKEN") and os.getenv("SYSTEM_DEFINITIONID")):
        return []
    try:
        runs = ado("GET", f"build/builds?definitions={os.environ['SYSTEM_DEFINITIONID']}"
                          f"&statusFilter=completed&$top={top}&api-version=7.1")["value"]
    except Exception as exc:  # noqa: BLE001 - history is advisory; never block on it
        return [f"history unavailable ({exc.__class__.__name__})"]
    found = []
    durations = []
    for r in runs:
        if r.get("startTime") and r.get("finishTime"):
            start, end = parse_ts(r["startTime"]), parse_ts(r["finishTime"])
            durations.append((end - start).total_seconds() / 60)
    if len(durations) >= 5:
        med = statistics.median(durations)
        if durations[0] > 1.5 * med:
            found.append(f"last run took {durations[0]:.1f} min vs median {med:.1f} min")
    failed = sum(1 for r in runs if r.get("result") == "failed")
    if runs and failed / len(runs) > 0.3:
        found.append(f"{failed}/{len(runs)} recent runs failed (>30%)")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", default="test-results.xml")
    ap.add_argument("--coverage", default="coverage.xml")
    ap.add_argument("--static-analysis", default=os.getenv("QUALITY_GATE", "NONE"), help="OK | ERROR | NONE")
    ap.add_argument("--critical-vulns", type=int, default=int(os.getenv("CRITICAL_VULNS", "0")))
    ap.add_argument("--since", default=os.getenv("LAST_RELEASE_REF", ""), help="last release tag/commit")
    ap.add_argument("--min-coverage", type=float, default=80)
    ap.add_argument("--min-trace", type=float, default=90)
    ap.add_argument("--max-risk", type=int, default=60, help="risk >= this is NO-GO (split the release)")
    ap.add_argument("--out", default="release-readiness.md")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--enforce", action="store_true", help="exit 1 on NO-GO")
    a = ap.parse_args()

    t = junit(a.junit)
    cov = coverage(a.coverage)
    commits, files, added, deleted = change_set(a.since)
    traced = [c for c in commits if WI_REF.search(c[2])]
    trace_pct = round(100 * len(traced) / len(commits), 1) if commits else 100.0
    work_items = sorted({int(m) for c in commits for m in WI_REF.findall(c[2])})
    src_changed = [f for f in files if f.endswith(SRC_EXT) and not f.startswith("tests/")]
    tests_changed = [f for f in files if f.startswith("tests/")]
    hot = hotspots(files)
    odd = anomalies()

    # Transparent, rule-based risk score (0 = low, 100 = high). Shown next to the AI narrative.
    risk = min(100, round(
        min(added + deleted, 1000) / 20          # size: up to 50 points
        + 10 * len(hot)                         # hot files touched: 10 each
        + (15 if src_changed and not tests_changed else 0)   # code changed, no tests changed
        + (10 if t["skipped"] else 0)
        + 10 * len(odd)))
    risk_band = "Low" if risk < 30 else "Medium" if risk < 60 else "High"

    gates = [
        ("All tests pass", t["failed"] == 0,
         f"{t['tests']} run, {t['failed']} failed, {t['skipped']} skipped"),
        (f"Line coverage >= {a.min_coverage:g}%", cov >= a.min_coverage, f"{cov}%"),
        ("Static analysis gates passed", a.static_analysis in ("OK", "NONE"),
         a.static_analysis + (" (not configured)" if a.static_analysis == "NONE" else "")),
        ("No critical vulnerabilities", a.critical_vulns == 0, str(a.critical_vulns)),
        (f"Commits traced to work items >= {a.min_trace:g}%", trace_pct >= a.min_trace,
         f"{trace_pct}% ({len(traced)}/{len(commits)})"),
        (f"Rule-based risk score < {a.max_risk}", risk < a.max_risk, f"{risk}/100 ({risk_band})"),
    ]
    decision = "GO" if all(ok for _, ok, _ in gates) else "NO-GO"

    signals = {"tests": t, "coverage": cov, "static_analysis": a.static_analysis, "critical_vulns": a.critical_vulns,
               "commits": [f"{sha} {subject}" for sha, subject, _ in commits],
               "files_changed": dict(files), "lines_added": added,
               "lines_deleted": deleted, "hotspots": hot, "traceability_pct": trace_pct,
               "work_items": work_items, "anomalies": odd, "rule_risk_score": risk,
               "decision": decision}

    ai_risk = ask(
        "You assess release risk for a web API. Use ONLY the JSON signals given. "
        "Write <=150 words: the 3 biggest risks, each with the evidence from the signals, then one "
        "line 'Suggested focus for the approver:'. Do not state GO or NO-GO; humans decide.",
        json.dumps(signals), dry_run=a.dry_run)
    notes = ask(
        "Draft release notes from these commit messages. Group under '#### Features', '#### Fixes', "
        "'#### Other'. Keep each item to one line and keep the work item reference (#123). "
        "Do not invent items.", "\n".join(body.strip() for _, _, body in commits), dry_run=a.dry_run)

    rows = "\n".join(f"| {name} | {'PASS' if ok else 'FAIL'} | {ev} |" for name, ok, ev in gates)
    hot_txt = ", ".join(f"`{f}` ({n} changes/90d)" for f, n in hot) or "none"
    md = f"""# Release readiness - build {os.getenv('BUILD_BUILDNUMBER', 'local')}

## Recommendation: **{decision}**  (rule-based; final decision = human approver)

| Gate | Result | Evidence |
|---|---|---|
{rows}

**Change set:** {len(commits)} commits, {len(files)} files, +{added}/-{deleted} lines.
**Work items:** {', '.join('#' + str(w) for w in work_items) or 'none'}.
**Hotspots touched:** {hot_txt}.
**Pipeline anomalies:** {'; '.join(odd) or 'none detected'}.
**Rule-based risk score:** {risk}/100 ({risk_band}).

## AI risk summary
{BANNER}{ai_risk}

## Draft release notes
{BANNER}{notes}
"""
    with open(a.out, "w") as f:
        f.write(md)
    with open("release-readiness.json", "w") as f:
        json.dump(signals, f, indent=2)
    print(md)
    upload_summary(a.out)
    print(f"##vso[task.setvariable variable=decision;isOutput=true]{decision}")
    print(f"##vso[task.setvariable variable=riskScore;isOutput=true]{risk}")
    if a.enforce and decision == "NO-GO":
        print("##vso[task.logissue type=error]Release readiness is NO-GO - see the summary tab.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
