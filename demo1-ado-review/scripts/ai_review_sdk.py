#!/usr/bin/env python3
"""AI peer review of a pull request, using the Foundry Local Python SDK.

This is the SDK version of ai_review.py. Same logic, same output, but the model
lifecycle (service start, model download, hardware detection, endpoint discovery)
is handled by FoundryLocalManager instead of env vars and raw HTTP.

Show this version on your laptop. Show ai_review.py in the pipeline. The
difference is the point: six lines to set up versus twenty, same review
findings either way.

Requires:
    pip install foundry-local-sdk

Usage:
    python3 ai_review_sdk.py --dry-run --diff-base origin/main
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    from foundry_local_sdk import Configuration, FoundryLocalManager
except ImportError:
    sys.exit("missing dependencies. run: pip install foundry-local-sdk\n"
             "or use scripts/ai_review.py, which needs nothing installed.")

SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}
BLOCKING = {"blocker"}


# ---------------------------------------------------------------- setup
# Six lines, once you are inside main(). The manager starts the service if it
# isn't running, the catalog resolves an alias to the best variant for your
# hardware, and the model downloads, loads, and hands you a chat client.
#
# Two things this deliberately does NOT do:
#
#   1. Run at import time. Initializing the manager starts a service and can
#      pull gigabytes of weights. Doing that on import means `--help` downloads
#      a model, which is rude.
#   2. Read FOUNDRY_MODEL. That variable holds the FULL model id with a version
#      suffix (e.g. Phi-4-mini-instruct-generic-gpu:5) because the raw HTTP
#      script needs it. The catalog wants an ALIAS. Passing a full id here
#      fails. Use FOUNDRY_ALIAS if you want to override.

DEFAULT_ALIAS = "phi-4-mini"

chat = None
model_id = None


def init_model():
    """Start Foundry Local and return (chat, model_id). Called from main()."""
    global chat, model_id
    alias = os.environ.get("FOUNDRY_ALIAS", DEFAULT_ALIAS)
    print(f"  starting Foundry Local for alias '{alias}' ...")

    FoundryLocalManager.initialize(Configuration(app_name="ai_review"))
    manager = FoundryLocalManager.instance

    model = manager.catalog.get_model(alias)
    if not model.is_cached:
        print("  downloading weights (first run only) ...")
        model.download()
    model.load()

    chat = model.get_chat_client()
    chat.settings.temperature = 0.0
    chat.settings.max_tokens = 4096

    model_id = getattr(model, "id", None) or getattr(model, "name", None) or alias
    print(f"  model    {model_id}")
    return chat, model_id


# ---------------------------------------------------------------- git
# Every git call runs with cwd=repo root. `git diff --name-only` prints paths
# relative to the root, but a `-- <path>` pathspec resolves against the current
# working directory. Mixing the two means that running this script from a
# subdirectory silently matches nothing: every diff comes back empty, every
# file is skipped, and the run reports zero findings and exits 0. A review that
# did not happen must not look like a pass, so both calls get the same cwd.

def repo_root():
    return subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=True).stdout.strip()


def changed_files(base, patterns, root):
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         cwd=root, capture_output=True, text=True,
                         check=True).stdout
    files = [f for f in out.splitlines() if f.strip()]
    if not patterns:
        return files
    keep = []
    for f in files:
        if any(re.search(p, f) for p in patterns):
            keep.append(f)
    return keep


def file_diff(base, path, root):
    return subprocess.run(["git", "diff", f"{base}...HEAD", "--", path],
                          cwd=root, capture_output=True, text=True,
                          check=True).stdout


# ---------------------------------------------------------------- model

def review_file(system_prompt, path, diff, max_chars=12000):
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n[diff truncated for review]"

    t0 = time.time()
    response = chat.complete_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"File: {path}\n\nUnified diff:\n{diff}"},
    ])
    text = response.choices[0].message.content
    return parse_findings(text, path), round(time.time() - t0, 1)


def parse_findings(text, path):
    """Tolerant parse. A model that returns garbage produces zero findings, not
    a crash, and the run is marked degraded so the pipeline can fail closed."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        start, end = text.find("{"), text.rfind("}")
        if start == -1:
            return None
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
        raw = obj.get("findings", [])
    else:
        try:
            raw = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

    out = []
    for f in raw if isinstance(raw, list) else []:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity", "")).lower()
        if sev not in SEVERITY_ORDER:
            continue
        msg = str(f.get("message", "")).strip()
        if not msg:
            continue
        out.append({"path": path, "severity": sev, "message": msg[:600],
                    "line": f.get("line"), "rule": str(f.get("rule", ""))[:60]})
    return out


# ---------------------------------------------------------------- azure devops

def post_thread(finding, dry_run):
    body = (f"**{finding['severity'].upper()}**"
            f"{' · `' + finding['rule'] + '`' if finding['rule'] else ''}\n\n"
            f"{finding['message']}\n\n"
            f"<sub>Reviewed locally by `{model_id}` on this build agent. "
            f"No source code left the machine.</sub>")

    if dry_run:
        line = f" line {finding['line']}" if finding.get("line") else ""
        print(f"    [{finding['severity']:<7}] {finding['path']}{line}\n"
              f"              {finding['message'][:160]}")
        return True

    org = os.environ["SYSTEM_COLLECTIONURI"].rstrip("/")
    project = os.environ["SYSTEM_TEAMPROJECT"]
    repo = os.environ["BUILD_REPOSITORY_ID"]
    pr = os.environ["SYSTEM_PULLREQUEST_PULLREQUESTID"]
    token = os.environ["SYSTEM_ACCESSTOKEN"]

    url = (f"{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{pr}"
           f"/threads?api-version=7.1")
    thread = {
        "comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
        "status": 1,
        "threadContext": {
            "filePath": "/" + finding["path"].lstrip("/"),
            "rightFileStart": {"line": finding.get("line") or 1, "offset": 1},
            "rightFileEnd": {"line": finding.get("line") or 1, "offset": 2},
        },
    }
    auth = base64.b64encode(f":{token}".encode()).decode()
    req = urllib.request.Request(url, data=json.dumps(thread).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Basic {auth}"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(f"    post failed {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        if e.code in (203, 401, 403):
            print("    hint: grant the build service 'Contribute to pull requests'",
                  file=sys.stderr)
        return False


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff-base", default=os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH", "origin/main"))
    ap.add_argument("--prompt", default=os.path.join(os.path.dirname(__file__), "..", "prompts", "mulesoft-review.md"))
    ap.add_argument("--paths", default=os.path.join(os.path.dirname(__file__), "..", "review-paths.txt"))
    ap.add_argument("--dry-run", action="store_true", help="print findings, post nothing")
    ap.add_argument("--fail-on", default="blocker", choices=["blocker", "major", "minor", "never"])
    args = ap.parse_args()

    init_model()

    base = args.diff_base
    if base.startswith("refs/heads/"):
        base = "origin/" + base[len("refs/heads/"):]

    with open(args.prompt) as f:
        system_prompt = f.read()

    patterns = []
    if os.path.exists(args.paths):
        with open(args.paths) as f:
            patterns = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    root = repo_root()
    files = changed_files(base, patterns, root)
    print(f"  reviewing {len(files)} file(s) against {base}")
    if not files:
        print("  nothing in scope")
        return 0

    findings, degraded = [], []
    for path in files:
        diff = file_diff(base, path, root)
        if not diff.strip():
            print(f"  {path}  no textual diff, skipped")
            continue
        try:
            result, secs = review_file(system_prompt, path, diff)
        except Exception as e:
            print(f"  ERROR  local model unreachable: {e}", file=sys.stderr)
            print("  failing closed: a review that did not happen is not a pass", file=sys.stderr)
            return 2
        if result is None:
            degraded.append(path)
            print(f"  {path}  unparseable model output ({secs}s)")
            continue
        findings.extend(result)
        print(f"  {path}  {len(result)} finding(s) in {secs}s")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["path"]))
    print(f"\n  {len(findings)} finding(s) total\n")
    for f in findings:
        post_thread(f, args.dry_run)

    if degraded:
        print(f"\n  degraded: {len(degraded)} file(s) produced no usable review", file=sys.stderr)
        return 2

    if args.fail_on == "never":
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    blocking = [f for f in findings if SEVERITY_ORDER[f["severity"]] <= threshold]
    if blocking:
        print(f"  {len(blocking)} finding(s) at or above '{args.fail_on}'. Failing the build.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
