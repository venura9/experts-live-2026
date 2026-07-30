"""THE INVARIANT. Read this file first.

    The model can stop trading. The model can never start trading.

Everything else in this project exists to serve that sentence. The gate is the
only place that decides whether an order may be placed, and it returns False
for every condition it does not explicitly understand.

Five ways to be blocked, in the order evaluate() checks them:
  1. No record at all               -> blocked  NO_SIGNAL
  2. Record older than max_age      -> blocked  STALE
  3. Record carries no valid signal -> blocked  UNPARSED
  4. Signal says halt               -> blocked  HALT
  5. Confidence below floor         -> blocked  LOW_CONFIDENCE

Note what is missing from that list: there is no code path where the model's
output causes a trade to happen. A trade happens because the strategy wanted
one and the gate did not object. Absence of objection is not authority.
"""
import time

DEFAULT_MAX_AGE = 900          # seconds
DEFAULT_MIN_CONFIDENCE = 0.60


class Decision:
    __slots__ = ("allowed", "reason", "code")

    def __init__(self, allowed, code, reason):
        self.allowed = allowed
        self.code = code
        self.reason = reason

    def to_dict(self):
        return {"allowed": self.allowed, "code": self.code, "reason": self.reason}


class Gate:
    def __init__(self, max_age=DEFAULT_MAX_AGE, min_confidence=DEFAULT_MIN_CONFIDENCE):
        self.max_age = max_age
        self.min_confidence = min_confidence

    def evaluate(self, record, now=None):
        """record is the latest ledger entry, or None."""
        now = now if now is not None else time.time()

        if record is None:
            return Decision(False, "NO_SIGNAL",
                            "No risk signal on file. Failing closed.")

        age = now - record.get("ts", 0)
        if age > self.max_age:
            return Decision(False, "STALE",
                            f"Signal is {int(age)}s old, limit is {self.max_age}s. Failing closed.")

        sig = record.get("signal")
        if not sig:
            return Decision(False, "UNPARSED",
                            "Last classification produced no valid signal. Failing closed.")

        if sig.get("halt"):
            return Decision(False, "HALT",
                            f"Sentinel halted trading: {sig.get('reason', '')}")

        conf = sig.get("confidence", 0.0)
        if conf < self.min_confidence:
            return Decision(False, "LOW_CONFIDENCE",
                            f"Confidence {conf} below floor {self.min_confidence}. Failing closed.")

        return Decision(True, "CLEAR",
                        f"Clear at confidence {conf}: {sig.get('reason', '')}")
