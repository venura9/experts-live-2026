#!/usr/bin/env python3
"""Risk Sentinel. Single entrypoint. Standard library only, no pip install.

  python3 run.py doctor
  python3 run.py classify "<announcement text>"
  python3 run.py classify --file scenarios/03_exchange_incident.txt
  python3 run.py bot --cycles 20 --interval 2
  python3 run.py ledger

Add --mock anywhere to run with no model at all (rehearsal on a plane).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_doctor(args):
    from sentinel import foundry
    try:
        h = foundry.health()
    except foundry.FoundryError as e:
        print(f"  mode      LIVE")
        print(f"  endpoint  {os.environ.get('FOUNDRY_URL', 'http://localhost:5273/v1')}")
        print(f"\n  DEGRADED  {e}")
        print("  hint      foundry server start, then re-read the port from foundry status")
        print("            or rehearse offline with: python3 run.py --mock doctor")
        return 1
    print(f"  mode      {h['mode']}")
    print(f"  endpoint  {h['url']}")
    print(f"  model     {h['model']}")
    if h["mode"] == "LIVE":
        print(f"  loaded    {', '.join(h.get('loaded', [])) or '(none)'}")
        print(f"  latency   {h['latency_s']}s")
    if h["ok"]:
        print("\n  READY")
        return 0
    print(f"\n  DEGRADED  {h.get('hint','')}")
    return 1


def cmd_classify(args):
    from bot import engine
    from sentinel.classify import classify

    text = args.text
    if args.file:
        with open(args.file) as f:
            text = f.read().strip()
    if not text:
        print("nothing to classify")
        return 2

    print(f"\n  announcement: {text[:120]}{'...' if len(text) > 120 else ''}\n")
    sig, records = classify(text)
    for r in records:
        if r.get("ok"):
            print(f"  attempt {r['attempt']}  accepted in {r['elapsed_s']}s")
        else:
            print(f"  attempt {r['attempt']}  REJECTED: {r.get('error')}")

    engine.append("classification", {
        "announcement": text,
        "signal": sig.to_dict() if sig else None,
        "attempts": records,
    })

    if sig is None:
        print("\n  no valid signal produced. The gate will fail closed.")
        return 1
    print(f"\n  halt={sig.halt}  severity={sig.severity}  confidence={sig.confidence}")
    print(f"  reason: {sig.reason}")
    return 0


def cmd_bot(args):
    from bot.engine import Engine, latest_signal
    from bot.gate import Gate

    gate = Gate(max_age=args.max_age, min_confidence=args.min_confidence)

    def heartbeat():
        from sentinel import foundry
        if os.environ.get("SENTINEL_MOCK") == "1":
            return True
        try:
            foundry.models()
            return True
        except foundry.FoundryError:
            return False

    eng = Engine(gate, seed=args.seed, heartbeat=heartbeat)

    srv = None
    if not args.no_web:
        from web import server
        srv = server.serve(args.port)
        print(f"  dashboard  http://127.0.0.1:{args.port}")

    def publish(i, result):
        d = result["decision"]
        rec = latest_signal()
        sig = (rec or {}).get("signal") or {}
        age = None if not rec else int(time.time() - rec.get("ts", 0))
        line = f"cycle {i+1:>3}  {result['action']:<8} {d['code']:<15} {d['reason'][:70]}"
        print("  " + line)
        if srv:
            from web import server
            server.publish(gate=d, signal=sig, age_s=age,
                           counters={"placed": eng.placed, "blocked": eng.blocked},
                           mock=os.environ.get("SENTINEL_MOCK") == "1")
            server.push_event(line)

    print()
    totals = eng.run(args.cycles, args.interval, on_cycle=publish)
    print(f"\n  placed {totals['placed']}   blocked {totals['blocked']}")
    if srv and args.hold:
        print("  holding dashboard, ctrl-c to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_reset(args):
    """Wipe the ledger. A stale ledger from the last rehearsal will happily feed
    the gate a fresh-looking CLEAR signal and hide a broken demo."""
    from bot import engine
    if os.path.exists(engine.LEDGER):
        os.remove(engine.LEDGER)
        print(f"  removed  {engine.LEDGER}")
    else:
        print("  ledger already empty")
    return 0


def cmd_ledger(args):
    from bot.engine import read_all
    for e in read_all()[-args.tail:]:
        ts = time.strftime("%H:%M:%S", time.localtime(e["ts"]))
        print(f"  {ts}  {e['kind']:<15} {str(e.get('gate') or e.get('signal') or '')[:110]}")
    return 0


def main():
    # --mock lives on a shared parent so it works on either side of the
    # subcommand. Under stage pressure you will type it in the wrong place.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mock", action="store_true",
                        help="no model calls, deterministic canned answers")

    p = argparse.ArgumentParser(prog="run.py", description="Risk Sentinel",
                                parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="pre-flight check", parents=[common]).set_defaults(fn=cmd_doctor)

    sub.add_parser("reset", help="wipe the ledger before a rehearsal or a run",
                   parents=[common]).set_defaults(fn=cmd_reset)

    c = sub.add_parser("classify", help="classify one announcement", parents=[common])
    c.add_argument("text", nargs="?", default="")
    c.add_argument("--file")
    c.set_defaults(fn=cmd_classify)

    b = sub.add_parser("bot", help="run the dry-run trading loop", parents=[common])
    b.add_argument("--cycles", type=int, default=20)
    b.add_argument("--interval", type=float, default=2.0)
    b.add_argument("--max-age", type=int,
                   default=int(os.environ.get("SENTINEL_MAX_AGE", "60")),
                   help="signal staleness limit in seconds. 60 so staleness "
                        "bites while the room is watching. Production would be 900")
    b.add_argument("--min-confidence", type=float, default=0.60)
    b.add_argument("--seed", type=int, default=None)
    b.add_argument("--port", type=int, default=8099)
    b.add_argument("--no-web", action="store_true")
    b.add_argument("--hold", action="store_true", help="keep the dashboard up after the last cycle")
    b.set_defaults(fn=cmd_bot)

    l = sub.add_parser("ledger", help="print the audit trail", parents=[common])
    l.add_argument("--tail", type=int, default=20)
    l.set_defaults(fn=cmd_ledger)

    args = p.parse_args()
    # argparse gotcha: --mock exists on both the top-level parser and each
    # subparser, so whichever one is parsed last writes to args.mock and can
    # clobber a True with its own False default. Check argv directly instead.
    if args.mock or "--mock" in sys.argv:
        os.environ["SENTINEL_MOCK"] = "1"
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
