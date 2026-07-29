"""Signal schema, strict validation, and the system prompt.

The model is not trusted. Everything it returns passes through here first.
Anything malformed, contradictory or out of range is rejected outright, and a
rejected signal is treated exactly like no signal at all: the bot stops.
"""
import json
import re

SEVERITIES = ("none", "low", "medium", "high")

SYSTEM = """You classify cryptocurrency exchange announcements for an automated trading system.

Decide one thing only: whether the trading system should HALT.

Halt if the announcement describes anything that could affect order execution,
settlement, withdrawals, deposits, API availability, or the listing status of a
traded pair. When uncertain, halt.

Do not halt for marketing, new feature launches, blog posts, or maintenance that
has already completed with no impact.

Respond with a single JSON object and nothing else. No prose, no code fences.

{"halt": <true|false>, "confidence": <0.0-1.0>, "severity": "none|low|medium|high", "reason": "<one short sentence>"}

Rules you must not break:
- halt=true requires severity of low, medium or high.
- halt=false requires severity "none".
- reason must be your own short summary of WHY you decided, under 120
  characters. Do not copy or restate the announcement text. Ground it in what
  the announcement actually says; do not invent facts.

Examples of a good reason:
  "Exchange reports an unscheduled incident affecting execution"
  "Routine notice with no stated trading impact"
  "Wording is ambiguous about whether trading is affected"
"""


class SchemaError(ValueError):
    pass


class Signal:
    __slots__ = ("halt", "confidence", "severity", "reason", "raw")

    def __init__(self, halt, confidence, severity, reason, raw=""):
        self.halt = halt
        self.confidence = confidence
        self.severity = severity
        self.reason = reason
        self.raw = raw

    def to_dict(self):
        return {"halt": self.halt, "confidence": self.confidence,
                "severity": self.severity, "reason": self.reason}

    def __repr__(self):
        return f"Signal(halt={self.halt}, conf={self.confidence}, sev={self.severity})"


def _extract(text):
    """Small models sometimes wrap JSON in fences or chatter. Take the object."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise SchemaError("no JSON object in response")
    return text[start:end + 1]


def parse(text):
    """Parse and validate. Raises SchemaError on anything suspicious."""
    try:
        obj = json.loads(_extract(text))
    except json.JSONDecodeError as e:
        raise SchemaError(f"invalid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise SchemaError("top level is not an object")

    missing = {"halt", "confidence", "severity", "reason"} - set(obj)
    if missing:
        raise SchemaError(f"missing keys: {sorted(missing)}")

    halt = obj["halt"]
    if not isinstance(halt, bool):
        raise SchemaError("halt is not a boolean")

    conf = obj["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        raise SchemaError("confidence is not a number")
    conf = float(conf)
    if not 0.0 <= conf <= 1.0:
        raise SchemaError(f"confidence out of range: {conf}")

    sev = obj["severity"]
    if sev not in SEVERITIES:
        raise SchemaError(f"unknown severity: {sev!r}")

    reason = obj["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise SchemaError("reason is empty")
    # The prompt asks for under 120. The gate accepts up to 200 so a marginally
    # chatty answer does not cost a retry, while a model that has simply echoed
    # the announcement back still gets rejected.
    if len(reason) > 200:
        raise SchemaError(f"reason too long: {len(reason)} chars, likely echoing the announcement")

    # Contradiction checks. These catch the failure mode small models actually
    # have: fluent output that disagrees with itself.
    if halt and sev == "none":
        raise SchemaError("contradiction: halt=true with severity none")
    if not halt and sev != "none":
        raise SchemaError(f"contradiction: halt=false with severity {sev}")

    return Signal(halt, round(conf, 3), sev, reason.strip(), raw=text)
