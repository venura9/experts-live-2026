"""Classification with a retry-and-complain policy.

One retry on a schema failure, with the validator's complaint fed back to the
model. If the second attempt also fails, we return nothing. Nothing is a safe
answer here, because the gate fails closed on a missing signal.
"""
import time

from . import foundry
from .schema import SYSTEM, SchemaError, parse


def classify(announcement, attempts=2):
    """Returns (signal_or_None, list_of_attempt_records)."""
    records = []
    user = announcement
    for i in range(attempts):
        try:
            text, elapsed = foundry.complete(SYSTEM, user)
        except foundry.FoundryError as e:
            records.append({"attempt": i + 1, "error": f"transport: {e}", "elapsed_s": 0})
            return None, records
        try:
            sig = parse(text)
            records.append({"attempt": i + 1, "ok": True, "elapsed_s": round(elapsed, 2),
                            "signal": sig.to_dict()})
            return sig, records
        except SchemaError as e:
            records.append({"attempt": i + 1, "ok": False, "elapsed_s": round(elapsed, 2),
                            "error": str(e), "raw": text[:300]})
            user = (f"{announcement}\n\nYour previous response was rejected: {e}\n"
                    f"Return only the JSON object described in the system prompt.")
            time.sleep(0.2)
    return None, records
