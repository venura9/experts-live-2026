# Numbers for the deck

Two kinds here. Cite the first, generate the second yourself the morning of the
talk. Numbers you measured on the laptop in your hand beat numbers you read.

## Cite these

| Number | What it is | Source |
|---|---|---|
| ~20 MB | Size of the Foundry Local runtime package | microsoft/Foundry-Local README |
| 9 April 2026 | General availability date | Foundry blog, GA announcement |
| 19 May 2025 | Public preview announced at Build | same |
| 3 platforms | Windows, macOS Apple Silicon, Linux (x64 and ARM64) | Microsoft Learn |
| 4 SDKs | C#, JavaScript, Python, Rust | repo README |
| 2.4k / 330 | GitHub stars / forks on microsoft/Foundry-Local | GitHub, 29 Jul 2026. Re-check the morning of, it moves |
| $0 | Per-token cost, API keys, and Azure subscription required | repo README |
| 0 bytes | Source code leaving the build agent in Demo 1 | your own pipeline |

## Generate these on your own hardware

`python3 bench.py` writes a small table you can paste straight onto a slide:
tokens per second, time to first token, and cold vs warm model load on the exact
machine you are presenting from.

Do this twice, once with wifi on and once with it off, and put both on the slide.
The identical numbers are the argument.

## The comparison slide that lands

For the PR review demo, the honest framing is cost and exposure, not speed.

| | Cloud LLM review | Foundry Local review |
|---|---|---|
| Code leaves the boundary | Yes | No |
| Per-review cost | Per-token | Zero marginal |
| Works with egress blocked | No | Yes |
| Latency | Network round trip | Local |
| Model quality ceiling | Frontier | Small model, narrow task |
| Approval needed from security | Usually months | Usually none |

That last row is the one that gets the laugh and the nod. Do not skip it.

## Caveat to say out loud

Third-party tokens-per-second benchmarks for local models vary wildly by
quantisation, context length and thermal state. If you quote someone else's
number, say whose it is. If you quote your own, say what hardware. The room in a
regulated-industry talk is exactly the room that will fact-check you.
