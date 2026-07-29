"""Append-only ledger and a dry-run trading loop.

The strategy here is deliberately worthless: it flips a seeded coin. Nothing in
this demo should compete for attention with the gate. What matters is that every
cycle asks the gate first, and every decision is written down before anything
else happens.
"""
import json
import os
import random
import time

STATE = os.environ.get("SENTINEL_STATE", "./state")
LEDGER = os.path.join(STATE, "ledger.jsonl")


def _ensure():
    os.makedirs(STATE, exist_ok=True)


def append(kind, payload):
    """Append-only, fsynced. An audit trail you cannot quietly rewrite."""
    _ensure()
    entry = {"ts": time.time(), "kind": kind}
    entry.update(payload)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def read_all():
    _ensure()
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def latest_signal():
    """Most recent classification entry, valid or not."""
    for e in reversed(read_all()):
        if e.get("kind") == "classification":
            return e
    return None


class Engine:
    """Dry run only. No exchange credentials exist anywhere in this project."""

    def __init__(self, gate, seed=None, heartbeat=None):
        self.gate = gate
        self.rng = random.Random(seed)
        self.placed = 0
        self.blocked = 0
        # heartbeat() -> True if the sentinel is answering, False if not.
        # Without this the loop only ever reads the ledger, so killing the model
        # changes nothing until the signal ages out. That is a fail-open window.
        self.heartbeat = heartbeat

    def cycle(self):
        want = self.rng.random() < 0.7

        # Liveness first. A control that cannot be reached is not a control, and
        # silence must be written down rather than inferred from an old record.
        if self.heartbeat is not None and not self.heartbeat():
            append("classification", {
                "announcement": "(heartbeat)",
                "signal": None,
                "attempts": [{"attempt": 1, "error": "transport: sentinel unreachable"}],
            })

        record = latest_signal()
        decision = self.gate.evaluate(record)

        if not want:
            return {"action": "none", "decision": decision.to_dict(),
                    "note": "strategy had no order this cycle"}

        if decision.allowed:
            self.placed += 1
            entry = append("order", {"side": self.rng.choice(["buy", "sell"]),
                                     "pair": "ETH/AUD", "dry_run": True,
                                     "gate": decision.to_dict()})
            return {"action": "placed", "decision": decision.to_dict(), "entry": entry}

        self.blocked += 1
        append("blocked", {"gate": decision.to_dict()})
        return {"action": "blocked", "decision": decision.to_dict()}

    def run(self, cycles, interval, on_cycle=None):
        for i in range(cycles):
            result = self.cycle()
            if on_cycle:
                on_cycle(i, result)
            if i < cycles - 1:
                time.sleep(interval)
        return {"placed": self.placed, "blocked": self.blocked}
