# orders-api - STARTER repository (CGI Azure DevOps programme)

You build the pipelines, policies and gates yourself during the labs; `scripts/` and `infra/` are provided.

A deliberately small Flask API used by every lab from Module 1 to the Capstone.

| Path | Used in |
|---|---|
| `orders.py`, `app.py`, `tests/` | M1-M4 (stories #42, #57; unit + API tests) |
| `pipelines/pr-check.yml` | M2 trainer-supplied PR check that runs the tests |
| `ruff.toml` | M4 lint, bug-pattern and security rules with documented exceptions |
| `pipelines/templates/python-ci-steps.yml` | M3 template, M4 quality gates |
| `azure-pipelines.yml` | M3 CI -> M5 CD (dev, staging canary) -> M8 readiness -> production |
| `infra/` (`main.bicep`, `terraform/`), `.checkov.yaml`, `pipelines/infra.yml` | M6 IaC + DevSecOps |
| `pipelines/pr-ai-review.yml`, `scripts/ai_pr_summary.py`, `.azuredevops/pull_request_template.md` | M7 |
| `scripts/release_readiness.py`, `failure_triage.py`, `dora_metrics.py` | M8 |

Local run:

    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest --cov=app --cov=orders
    flask --app app run

Before you push: replace `136` with your training user number in `azure-pipelines.yml`,
`pipelines/*.yml` and `infra/main.bicepparam`.

No API keys anywhere: Azure OpenAI is called with Microsoft Entra ID (keyless).
