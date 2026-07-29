"""OpenAI-compatible client for Foundry Local. Standard library only.

Foundry Local's optional local web server speaks the OpenAI chat completions
shape, so this is the same code you would point at Azure AI Foundry, OpenAI or
anything else. That portability is the whole architectural point.
"""
import json
import os
import time
import urllib.error
import urllib.request

URL = os.environ.get("FOUNDRY_URL", "http://localhost:5273/v1")
MODEL = os.environ.get("FOUNDRY_MODEL", "phi-4-mini")
MOCK = os.environ.get("SENTINEL_MOCK") == "1"
TIMEOUT = float(os.environ.get("FOUNDRY_TIMEOUT", "60"))


class FoundryError(RuntimeError):
    pass


def _post(path, payload):
    req = urllib.request.Request(
        URL.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        raise FoundryError(f"cannot reach Foundry Local at {URL}: {e}") from e


def models():
    """List loaded models. Use the full model ID from here in chat calls."""
    try:
        with urllib.request.urlopen(URL.rstrip("/") + "/models", timeout=10) as r:
            return [m["id"] for m in json.loads(r.read().decode()).get("data", [])]
    except urllib.error.URLError as e:
        raise FoundryError(f"cannot reach Foundry Local at {URL}: {e}") from e


def complete(system, user, max_tokens=400):
    """Return (text, elapsed_seconds). Temperature 0, fixed seed.

    A risk control that gives different answers to identical input is not a
    control. Determinism is a requirement here, not a nicety.
    """
    if MOCK:
        return _mock(user), 0.4
    t0 = time.time()
    data = _post("/chat/completions", {
        "model": MODEL,
        "temperature": 0,
        "seed": 42,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    })
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise FoundryError(f"unexpected response shape: {data}") from e
    return text, time.time() - t0


def _mock(user):
    """Deterministic offline responses so the demo rehearses on a plane.

    Ordered checks: the benign markers are tested before the alarming keywords,
    because "withdrawal services resumed" is not an incident.
    """
    low = user.lower()
    benign = ("completed successfully", "resumed", "as planned",
              "no action is required", "introducing", "rolling out")
    alarming = ("unscheduled", "investigating", "incident", "delayed",
                "suspend", "delisting", "halted", "degraded")
    if any(k in low for k in benign) and not any(k in low for k in ("unscheduled", "investigating")):
        return json.dumps({"halt": False, "confidence": 0.88, "severity": "none",
                           "reason": "Routine notice with no stated trading impact"})
    if any(k in low for k in alarming):
        return json.dumps({"halt": True, "confidence": 0.91, "severity": "high",
                           "reason": "Exchange reports an unscheduled incident affecting execution"})
    return json.dumps({"halt": False, "confidence": 0.52, "severity": "none",
                       "reason": "No operational impact identified, low certainty"})


def health():
    """Pre-flight. Returns a dict the doctor command prints."""
    if MOCK:
        return {"ok": True, "mode": "MOCK", "url": URL, "model": MODEL, "latency_s": 0.0}
    t0 = time.time()
    ids = models()
    ok = MODEL in ids
    return {"ok": ok, "mode": "LIVE", "url": URL, "model": MODEL,
            "loaded": ids, "latency_s": round(time.time() - t0, 3),
            "hint": "" if ok else "Model not loaded. Use the full ID from /v1/models, not the alias."}
