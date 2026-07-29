# Experts Live 2026

### AI where your IP lives

Running language models on hardware you already control, for organisations that
cannot send their code to an AI service.

Session by [@venura9](https://github.com/venura9).

Everything demonstrated on stage is in this repo and runs on your own machine.
No API keys, no cloud account, no per-token cost.

---

## Try it in five minutes

```bash
# 1. Install Foundry Local
brew tap microsoft/foundrylocal && brew install foundrylocal   # macOS
# Linux: grab the release asset from github.com/microsoft/Foundry-Local/releases

# 2. Pull a small model
foundry model download phi-4-mini
foundry service status          # note the PORT

# 3. Run demo 2. No pip install, standard library only.
cd demo2-risk-sentinel
python3 run.py doctor
python3 run.py --mock bot --cycles 8 --interval 1
```

Demo 2 has a `--mock` mode, so you can see the whole thing work before you
install anything at all.

---

## The two demos

### 1. Pull request review inside Azure DevOps

A model reviews a MuleSoft pull request on the build agent itself. The diff
never reaches a model vendor. Findings post back as PR comment threads, and a
blocker fails the build so branch policy blocks the merge.

Two pipelines, because there are two different restrictions people are under:

| Pipeline | Agent | Answers |
|---|---|---|
| `azure-pipelines.yml` | self-hosted, in your network | "our code cannot leave our network" |
| `azure-pipelines-hosted.yml` | Microsoft-hosted `ubuntu-latest` | "we cannot get another AI vendor approved" |

The second is the more common restriction. If your repo is already in Azure
DevOps, Microsoft is already a processor for that code. Loading a model
in-process on the same agent adds no new vendor, no new DPA, no new egress
rule, and nothing to take through security review.

Two versions of the reviewer, too: `ai_review_sdk.py` uses the Foundry Local
Python SDK and sets up in three lines, `ai_review.py` is standard library only
for agents that cannot `pip install` at runtime. Identical findings.

### 2. A small model with authority to stop, never to start

A trading bot with a risk gate. The model can halt trading. It can never place
a trade. Asymmetric authority: give the small model the safe half of the
decision, so the worst case for a wrong answer is a false stop.

The pattern generalises well beyond trading. Hold a payment batch, never release
one. Freeze a deployment, never approve one. Kill a job on anomalous telemetry,
never launch one.

Everything fails closed. If the model is unreachable, unparseable or stale, the
gate blocks. Verify it yourself:

```bash
cd demo2-risk-sentinel
python3 run.py reset
FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web
# must read: placed 0
```

---

## Layout

```
deck.html                     the slides. One file, opens offline, no CDN
theme/                        the deck theme, reusable for your own talks
INSTALL.md                    platform matrix, install steps, pre-flight
RUNSHEET.md                   timings, beats, fallbacks, likely questions
STATS.md                      citable numbers and their sources
LINKS.md                      every URL from the deck
bench.py                      measure tokens/sec on your own hardware

demo1-ado-review/
  azure-pipelines.yml         self-hosted agent
  azure-pipelines-hosted.yml  Microsoft-hosted agent, with model caching
  scripts/ai_review.py        stdlib only
  scripts/ai_review_sdk.py    Foundry Local SDK
  prompts/mulesoft-review.md  review rules, versioned so behaviour is auditable
  review-paths.txt            scope control
  seed/seed_flaws.py          generates the MuleSoft app under review

demo2-risk-sentinel/
  run.py                      doctor | reset | classify | bot | ledger
  bot/gate.py                 the invariant. Read this file first
  sentinel/schema.py          strict validation, rejects contradictions
  web/                        dashboard, high contrast
  scenarios/                  four announcements, four gate outcomes
```

## The MuleSoft app

There isn't one checked in. `seed/seed_flaws.py` generates it: five files, about
330 lines, an Order API with an APIkit router, DataWeave transforms, a DB
config, TLS on the downstream call, and proper error handling on two of three
flows.

Five defects are planted in it. **None of them are commented in the source.**
Each is detectable only because it contradicts something the same codebase does
correctly.

```bash
python3 demo1-ado-review/seed/seed_flaws.py --list    # see them without writing files
python3 demo1-ado-review/seed/seed_flaws.py --dest ../order-api
```

Yes, the generated config contains a literal database password. That is defect
number one, it is fake, and it exists so the reviewer has something to find.

## The theme

`theme/` is the deck theme as a reusable starter: `theme.css`, `deck.js`,
`TEMPLATE.html` with one worked example of every layout, and a README. No web
fonts, no CDN, so it renders the same on a plane as on conference wifi.

```bash
cp -r theme my-talk && cd my-talk && mv TEMPLATE.html deck.html
```

Press `g` in any deck built on it to see every slide at once.

## Licence

MIT. Take the theme, take the demos, take the prompts. Attribution appreciated,
not required.
