"""Module 8: AI triage of a failed run - root-cause hints from the failed steps' logs.

Run in a job with condition: failed(). Needs SYSTEM_ACCESSTOKEN and the Azure OpenAI settings.
"""
import argparse
import os
import urllib.request

from aoai import BANNER, ado, ask, auth_header, upload_summary

LOG_TAIL = 120   # lines per failed step sent to the model


def fetch_log(url):
    req = urllib.request.Request(url)
    req.add_header("Authorization", auth_header())
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(errors="replace").splitlines()[-LOG_TAIL:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-file", help="offline mode: triage a local log file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    failed = []
    if a.log_file:
        failed.append(("local log", open(a.log_file).read().splitlines()[-LOG_TAIL:]))
    else:
        build_id = os.environ["BUILD_BUILDID"]
        timeline = ado("GET", f"build/builds/{build_id}/timeline?api-version=7.1")
        for rec in timeline.get("records", []):
            if rec.get("type") == "Task" and rec.get("result") == "failed" and rec.get("log"):
                failed.append((rec["name"], fetch_log(rec["log"]["url"])))

    if not failed:
        print("No failed task logs found.")
        return
    prompt = "\n\n".join(f"### Step: {name}\n" + "\n".join(lines) for name, lines in failed)
    hints = ask(
        "You triage CI/CD failures for an Azure Pipelines + Python + Azure App Service project. "
        "For each failed step give: likely root cause, the log line that shows it, the most likely "
        "fix, and a confidence (High/Medium/Low). If it looks environmental (permissions, quota, "
        "network, agent image), say so. Never invent log lines.", prompt, dry_run=a.dry_run)
    md = "# Failure triage\n\n" + BANNER + hints + "\n"
    with open("failure-triage.md", "w") as f:
        f.write(md)
    print(md)
    upload_summary("failure-triage.md")


if __name__ == "__main__":
    main()
