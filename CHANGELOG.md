# What changed on 29 July 2026

Everything below was verified against Microsoft Learn, the Foundry Local repo,
and the CLI release page on 29 July 2026.

## 1. CLI commands were NOT replaced (correction)

An earlier version of this package incorrectly claimed the CLI was rewritten in
June 2026 and renamed all commands. That was wrong. The official CLI reference
at learn.microsoft.com, last updated 15 July 2026, still documents:

    foundry service start / stop / restart / status / diag
    foundry model run / list / info / download / load / unload
    foundry cache remove / list / location

All commands in this package have been reverted to match the official docs.

## 2. macOS install is brew (correction)

The official docs still say `brew tap microsoft/foundrylocal && brew install
foundrylocal`. An earlier version of this package incorrectly claimed brew was
replaced by a signed .pkg. That was wrong. Reverted.

## 3. Linux is supported, x64 and ARM64

Foundry Local reached GA on 9 April 2026 with Linux support. Earlier material in
this package said Windows and macOS only.

This improves the Demo 1 story: a self-hosted ADO agent inside a locked-down
network is almost always a Linux VM, so you no longer have to explain why the
agent is a Mac. Update the enterprise hardening slide accordingly.

Honest caveat for stage: Linux ships CPU and CUDA execution providers only. It
does not get the NPU and iGPU breadth Windows gets through Windows ML. Say it
before someone asks.

## 4. Microsoft reframed the product as SDK-first

Foundry Local is now positioned as an embedded runtime you ship inside your app
(C#, JavaScript, Python, Rust), roughly 20 MB added to the bundle, with the
OpenAI-compatible local server described as optional and mainly for development
workflows and multi-process access.

Both demos here use the server. That is still the right choice for a pipeline
script and a background risk gate, but the framing slide now acknowledges both
shapes rather than presenting the server as the product.

## 5. Model aliases may move between releases

The scripts default to `phi-4-mini`. Run `foundry model list` on the machine you
are presenting from, pick what is actually there, and export the full ID from
`/v1/models`. The API needs the full ID; only the CLI takes aliases.

## 6. Port may not be 5273

Read the real port from `foundry service status` and export `FOUNDRY_URL`.

## Files touched

- `INSTALL.md` — rewritten macOS and Linux sections, new platform matrix, new pre-flight
- `deck.html` — platform slide and install slide, plus speaker notes
- `RUNSHEET.md` — pre-flight checklist, failure fallbacks, one new Q&A answer
- `STATS.md` — platform count
- `demo1-ado-review/README.md` — troubleshooting table

Python under `demo1-ado-review/` and `demo2-risk-sentinel/` was not changed. It
talks to the OpenAI-compatible endpoint over plain HTTP, which is unaffected by
the CLI rewrite.

---

# Demo verification, 29 July 2026

Both demos were run in the sandbox. Foundry Local is not installed there, so
live inference paths could not be exercised. Everything else was.

## Demo 1, ADO review: works, no code changes needed

Verified against a throwaway git repo with the seeded MuleSoft app on a branch:

- Diff detection and path filtering work
- With the model unreachable it fails closed cleanly, exit code 2, message
  "failing closed: a review that did not happen is not a pass"
- The pipeline definition correctly notes the two ADO traps: the `pr:` trigger
  does not work for Azure Repos (use a branch policy), and `SYSTEM_ACCESSTOKEN`
  must be mapped explicitly into the script step

One fix applied: `seed_flaws.py` wrote files at import time, so
`seed_flaws.py --help` silently seeded the current directory. It now has a real
argument parser, a `--dest` option, and refuses to overwrite without `--force`.

Two gaps to be aware of, neither a bug:

1. **No offline rehearsal path.** Unlike demo 2 there is no `--mock`. You cannot
   rehearse demo 1 without Foundry Local running.
2. **The MuleSoft app is generated, not shipped.** `seed_flaws.py` creates it.
   You still need to create the ADO repo, push the branch, open the PR, and wire
   the branch policy by hand. Allow an hour for that the first time.

## Demo 2, Risk Sentinel: had a demo-breaking bug, now fixed

**The bug.** The bot loop reads the latest classification from the ledger and
never calls the model itself. So killing the model produced silence, not a
signal, and silence was indistinguishable from a valid CLEAR until the record
aged past `--max-age`, which defaulted to 900 seconds.

Measured behaviour before the fix, with the endpoint pointed at a dead port:

```
cycle 1  none     CLEAR    Clear at confidence 0.88: Routine notice...
cycle 2  none     CLEAR    Clear at confidence 0.88: Routine notice...
cycle 3  placed   CLEAR    Clear at confidence 0.88: Routine notice...
placed 1   blocked 0
```

The signature beat of the talk, kill the model and watch it go red, went green
and placed an order. The gate logic in `gate.py` was correct throughout; nothing
was calling it with fresh information.

**Fixes applied:**

1. `Engine` takes a `heartbeat` callable. If the sentinel is unreachable, a
   classification record with a null signal is appended each cycle, which the
   gate reads as `UNPARSED` and blocks on.
2. `--max-age` now defaults to 60 seconds, overridable via `SENTINEL_MAX_AGE`.
   900 is right for production and wrong for a stage.
3. `run.py doctor` no longer throws a traceback when the endpoint is down. It
   prints DEGRADED with a hint. This was the command in the pre-flight
   checklist, so it failed in exactly the situation it existed to diagnose.
4. `--mock` now works on either side of the subcommand. `run.py doctor --mock`
   previously errored out.
5. New `run.py reset` to wipe the ledger. A leftover ledger from rehearsal is
   what masked the bug in the first place.

Measured behaviour after the fix, same dead endpoint:

```
cycle 1  none     UNPARSED  Last classification produced no valid signal. Failing closed.
cycle 2  blocked  UNPARSED  Last classification produced no valid signal. Failing closed.
cycle 3  none     UNPARSED  Last classification produced no valid signal. Failing closed.
placed 0   blocked 1
```

All four scripted beats verified end to end in mock mode: CLEAR with orders
flowing, HALT on the incident scenario, ledger output, and fail-closed on a dead
model. Dashboard serves HTTP 200 and `/api/state` returns correct JSON.
