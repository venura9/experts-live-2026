#!/usr/bin/env python3
"""Measure your own numbers for the stats slide. Standard library only.

  python3 bench.py
  python3 bench.py --runs 5 --tokens 200

Prints a markdown table you can paste into the deck.
"""
import argparse
import json
import os
import statistics
import time
import urllib.request

URL = os.environ.get("FOUNDRY_URL", "http://localhost:5273/v1")
MODEL = os.environ.get("FOUNDRY_MODEL", "phi-4-mini")

PROMPT = ("Explain in exactly one paragraph why running a language model on the "
          "same machine as a CI build agent changes the data governance story.")


def one(tokens):
    payload = {"model": MODEL, "temperature": 0, "seed": 42, "max_tokens": tokens,
               "messages": [{"role": "user", "content": PROMPT}]}
    req = urllib.request.Request(URL.rstrip("/") + "/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode())
    elapsed = time.time() - t0
    usage = data.get("usage") or {}
    out = usage.get("completion_tokens")
    if not out:
        out = max(1, len(data["choices"][0]["message"]["content"]) // 4)
    return elapsed, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--tokens", type=int, default=160)
    a = ap.parse_args()

    print(f"  endpoint {URL}\n  model    {MODEL}\n")
    cold, tok = one(a.tokens)
    print(f"  cold run  {cold:.2f}s")

    times, rates = [], []
    for i in range(a.runs):
        el, n = one(a.tokens)
        times.append(el)
        rates.append(n / el)
        print(f"  warm {i+1}    {el:.2f}s  {n} tokens  {n/el:.1f} tok/s")

    print("\n--- paste this ---\n")
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Model | `{MODEL}` |")
    print(f"| Cold start (first call) | {cold:.1f}s |")
    print(f"| Warm median latency | {statistics.median(times):.1f}s |")
    print(f"| Throughput | {statistics.median(rates):.0f} tok/s |")
    print(f"| Cost per call | $0.00 |")
    print(f"| Bytes of code sent off device | 0 |")


if __name__ == "__main__":
    main()
