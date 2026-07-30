# Risk Sentinel

A Foundry Local showcase built around one claim:

> You do not need a frontier model. You need a small model with a narrow job and
> a hard boundary.

A small model reads unstructured exchange announcements and decides one thing:
whether an automated trading bot should stop. The bot obeys. The model never
gets to say go.

Standard library only. No pip install, nothing to break on venue wifi.

For why the system is shaped this way, rather than how to run it, see
[DESIGN.md](DESIGN.md).

## Layout

```
run.py                  single entrypoint
bot/gate.py             THE INVARIANT. Read this one first
bot/engine.py           dry-run loop and append-only ledger
sentinel/foundry.py     OpenAI-compatible client, health check, mock mode
sentinel/schema.py      signal schema, strict validation, system prompt
sentinel/classify.py    retry-and-complain policy
web/                    stdlib dashboard, high contrast for projection
scenarios/              four announcements, four different gate outcomes
```

## Commands

```bash
python3 run.py doctor                                   # pre-flight, prints READY or DEGRADED
python3 run.py classify --file scenarios/01_routine.txt
python3 run.py bot --cycles 20 --interval 2 --hold      # dashboard on :8099
python3 run.py ledger --tail 20
```

Add `--mock` anywhere to run with no model at all. Mock mode announces itself in
the terminal and puts a yellow banner across the dashboard, so you cannot demo it
by accident.

## Config

| Knob | Where | Default |
|---|---|---|
| Endpoint | `FOUNDRY_URL` | `http://localhost:5273/v1` |
| Model | `FOUNDRY_MODEL` | `phi-4-mini` |
| State dir | `SENTINEL_STATE` | `./state` |
| Staleness limit | `bot --max-age` | 900s |
| Confidence floor | `bot --min-confidence` | 0.60 |
| Temperature | `sentinel/foundry.py` | 0.0, fixed seed |

Temperature is zero with a fixed seed on purpose. A risk control that gives
different answers to identical input is not a control.

## The four scenarios

| File | Model says | Gate |
|---|---|---|
| `01_routine.txt` | no impact, high confidence | CLEAR |
| `02_marketing.txt` | no impact, high confidence | CLEAR |
| `03_exchange_incident.txt` | halt, high severity | HALT |
| `04_ambiguous.txt` | no impact, low confidence | LOW_CONFIDENCE |

Plus two failure states you should demo deliberately: stop the model process for
`NO_SIGNAL`, and run with `--max-age 1` for `STALE`.

## What this is not

Not a trading strategy. The engine flips a seeded coin so nothing competes with
the point being made.

Not a claim that models should trade. It is the opposite claim, argued in code.


## Known-good verification

Run this before every rehearsal. Both lines matter.

```bash
python3 run.py reset

# happy path: orders flow
python3 run.py --mock classify --file scenarios/01_routine.txt
python3 run.py --mock bot --cycles 5 --interval 0 --no-web     # expect placed > 0

# fail-closed path: model unreachable, zero orders
python3 run.py reset
FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web
# expect: UNPARSED on every cycle, placed 0
```

If the second block ever places an order, the demo is broken and the thesis of
the talk is wrong on stage. Do not present until it reads zero.

## If a classification is REJECTED for reason length

The prompt used to say the reason must be under 140 characters **and** quote the
announcement. A small model cannot satisfy both, so it copies the announcement,
which blows the limit and costs you a retry on stage.

The prompt now asks for the model's own summary of why it decided, explicitly
tells it not to restate the announcement, and gives three worked examples. The
validator accepts up to 200 characters so a slightly chatty answer is not
rejected, while a full echo of the announcement still is.

If you still see rejections on a different model, look at the raw output in the
ledger before changing the limit. A model that echoes is a prompt problem; a
model that writes 300 characters of reasoning is a model-choice problem.

## Why the heartbeat exists

The bot loop reads the latest classification from the ledger; it does not call
the model itself. That is realistic, but it means a dead model produces silence
rather than a signal, and silence looked identical to a valid CLEAR until the
record aged past `--max-age`. With the old 900-second default that was a
15-minute window in which the bot happily kept trading with no risk control at
all.

`Engine` now takes a `heartbeat` callable. Each cycle, if the sentinel is
unreachable, a classification record with a null signal is appended, which the
gate reads as `UNPARSED` and blocks on. `--max-age` also defaults to 60 seconds
now, so staleness bites while the room is still watching.
