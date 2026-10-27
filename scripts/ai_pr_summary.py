"""Module 7: AI pull-request summary posted as a PR comment (human resolves it before merge).

Runs as a build-validation pipeline on PRs. Needs:
  checkout fetchDepth: 0, env SYSTEM_ACCESSTOKEN, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
  'Contribute to pull requests' = Allow for '<project> Build Service (<org>)' on the repo.
"""
import argparse
import os
import subprocess

from aoai import BANNER, ado, ask

MAX_DIFF_CHARS = 60_000   # keep the prompt within budget; larger diffs are truncated

SYSTEM = (
    "You are a senior reviewer for a Python Flask service. Review ONLY the diff given. "
    "Be specific, cite file names, never invent code that is not in the diff. "
    "Answer in Markdown with exactly these sections: "
    "### Summary (3-5 bullets of what changed and why), "
    "### Risks (bullets, each tagged [High]/[Medium]/[Low]), "
    "### Test gaps (behaviour changed without a matching test), "
    "### Questions for the author (max 3)."
)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.getenv("SYSTEM_PULLREQUEST_TARGETBRANCH", "refs/heads/main"))
    ap.add_argument("--dry-run", action="store_true", help="no AI call, no PR comment")
    a = ap.parse_args()

    target = "origin/" + a.target.removeprefix("refs/heads/")
    diff = git("diff", "--unified=3", f"{target}...HEAD")
    stat = git("diff", "--stat", f"{target}...HEAD")
    log = git("log", "--format=- %s", f"{target}..HEAD")
    truncated = len(diff) > MAX_DIFF_CHARS
    prompt = f"Commits:\n{log}\nDiffstat:\n{stat}\nDiff:\n{diff[:MAX_DIFF_CHARS]}"
    if truncated:
        prompt += "\n[diff truncated - say so in the Summary]"

    review = ask(SYSTEM, prompt, dry_run=a.dry_run)
    body = (BANNER + review + "\n\n---\n**Reviewer checklist (human):** "
            "resolve this thread only after you have checked every Risk and Test gap above.")
    with open("ai-pr-summary.md", "w") as f:
        f.write(body)
    print(body)

    pr_id = os.getenv("SYSTEM_PULLREQUEST_PULLREQUESTID")
    if a.dry_run or not pr_id:
        print("\n(no PR context or dry run: comment not posted)")
        return
    repo_id = os.environ["BUILD_REPOSITORY_ID"]
    ado("POST", f"git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.1",
        {"comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
         "status": 1})   # 1 = active: the 'comment resolution' policy blocks completion until resolved
    print(f"Posted AI summary to PR {pr_id}")


if __name__ == "__main__":
    main()
