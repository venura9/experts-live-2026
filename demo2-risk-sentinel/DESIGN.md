# Design notes

> The model can stop trading. It can never start trading.

Everything below is in service of that sentence. For the commands and the file
layout, see [README.md](README.md). This document is about why the system is
shaped this way.

## Why that is the interesting part

The obvious way to put an LLM in a trading system is to ask it what to buy.
That is a bad idea, and everyone already agrees it is a bad idea, so arguing
against it wins nothing. Nobody in the room needs convincing.

The interesting move is asymmetric authority. Give the small model only the safe
half of the decision: it can veto, and it can never initiate. The worst case for
a wrong answer is then a trade that did not happen. A missed trade is survivable
in a way that a wrong trade is not.

That reframes the question. "Can I trust a small model" has no answer you can
defend in a design review. "What is the blast radius when it is wrong" does, and
here the answer is small and boring by construction.

## The four parts

The **sentinel** classifies an announcement into strict JSON. It is the only
component that talks to the model.

The **ledger** is append-only and fsynced. Everything that happens is written
there before anything acts on it.

The **gate** is the only place that decides whether an order may be placed. It
returns False for every condition it does not explicitly understand.

The **strategy** flips a seeded coin. It is deliberately worthless, for two
reasons: nothing should compete with the gate for the audience's attention, and
a worthless strategy shows the gate works regardless of what the strategy wants.

## The five ways to be blocked

`Gate.evaluate` checks these in order and stops at the first one that fires:

| Code | Condition |
|---|---|
| `NO_SIGNAL` | no record at all |
| `STALE` | record older than `max_age` |
| `UNPARSED` | record exists but carries no valid signal |
| `HALT` | signal says halt |
| `LOW_CONFIDENCE` | confidence below the floor |

Now note what is absent from that list. There is no code path where model output
*causes* a trade. A trade happens because the strategy wanted one and the gate
did not object. Absence of objection is not authority.

## Three decisions worth defending

### Retry and complain

On a schema failure the sentinel retries once, and it feeds the validator's
actual complaint back into the prompt. Not "try again", but the specific
rejection: `contradiction: halt=true with severity none`, or
`confidence out of range: 1.4`. Small models correct well when told exactly what
was wrong with the previous attempt.

If the second attempt also fails, the sentinel returns nothing. Nothing is a
safe answer here, because the gate fails closed on a missing signal.

The part worth pointing at: both attempts, including the raw rejected text, are
appended to the ledger. Most retry loops exist to hide failure from whatever is
downstream. This one records it.

### The heartbeat

The bot loop reads the latest classification from the ledger. It does not call
the model itself. That separation is deliberate, and it created a bug.

A dead model produces silence, and silence was indistinguishable from a valid
CLEAR until the signal aged out. Between the model dying and `max_age`
expiring, the bot kept trading against a stale all-clear. Testing found it, not
review.

It is closed now. When the sentinel is unreachable, the loop appends a
null-signal record every cycle, and the gate reads that as `UNPARSED`. A control
that cannot be reached is not a control, and silence has to be written down
rather than inferred from an old record.

This is worth saying out loud when presenting. A demo that always worked is less
credible than one with a fail-open window that testing caught and closed.

### Write before you act

The ledger entry is fsynced before anything acts on it. The classification is
durable on disk before the gate ever reads it, and the outcome of every cycle is
written down too, including the blocks.

If the process dies mid-cycle, the record of what it decided survives. An audit
trail written after the fact is not an audit trail, it is a reconstruction.

## Where this generalises

The trading bot is the thing it was built on, not the point. The same shape
transfers wherever the safe direction is asymmetric:

Hold a payment batch, but never release one. Freeze a deployment, but never
approve one. Kill a job on anomalous telemetry, but never launch one.

In each case a wrong answer costs you a delay, and the expensive direction stays
under human or deterministic control.

## How to verify it yourself

Two runs. The first shows orders flowing, the second shows the fail-closed path
when the model is unreachable.

```bash
python3 run.py reset
python3 run.py --mock classify --file scenarios/01_routine.txt
python3 run.py --mock bot --cycles 5 --interval 0 --no-web     # expect placed > 0

python3 run.py reset
FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web
# expect: UNPARSED every cycle, placed 0
```

If the second block ever places an order, the demo proves the opposite of the
talk and must not be presented.
