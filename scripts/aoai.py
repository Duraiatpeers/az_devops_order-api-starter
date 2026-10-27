"""Shared helpers: keyless Azure OpenAI client + Azure DevOps REST calls.

No API keys. In a pipeline, run inside an AzureCLI@2 task: the Azure CLI is signed in with the
service connection's workload identity, and AzureCliCredential reuses that sign-in.
The identity needs the 'Cognitive Services OpenAI User' role on the Azure OpenAI resource.
"""
import base64
import json
import os
import urllib.parse
import urllib.request

API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
BANNER = "> **AI-generated (Azure OpenAI). Advisory only - a human must verify before acting on it.**\n\n"


def ask(system: str, user: str, dry_run: bool = False) -> str:
    """Send one chat request and return the text. dry_run returns a canned answer (offline testing)."""
    if dry_run or os.getenv("AI_DRY_RUN") == "1":
        return "[dry-run] AI output would appear here.\n- point one\n- point two"
    from azure.identity import AzureCliCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )
    # No max_tokens / temperature: newer models (gpt-5-mini, o-series) reject or restrict them.
    resp = client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],   # the *deployment* name, e.g. gpt-41-mini
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content.strip()


def auth_header() -> str:
    """Pipeline: System.AccessToken (Bearer). Local runs: a PAT in AZURE_DEVOPS_PAT (Basic)."""
    if os.getenv("SYSTEM_ACCESSTOKEN"):
        return "Bearer " + os.environ["SYSTEM_ACCESSTOKEN"]
    pat = os.environ["AZURE_DEVOPS_PAT"]
    return "Basic " + base64.b64encode(f":{pat}".encode()).decode()


def ado(method: str, path: str, body=None):
    """Call the Azure DevOps REST API with the pipeline's System.AccessToken."""
    base = os.environ["SYSTEM_TEAMFOUNDATIONCOLLECTIONURI"].rstrip("/")
    project = os.environ["SYSTEM_TEAMPROJECT"]
    url = f"{base}/{urllib.parse.quote(project)}/_apis/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth_header())
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def upload_summary(path: str):
    """Attach a markdown file to the run's Extensions/summary tab."""
    print(f"##vso[task.uploadsummary]{os.path.abspath(path)}")

