# Setup, from a bare machine to a working demo

Seven phases. Each has a checkpoint. Do not move on until it passes.

Written for macOS on Apple Silicon. Linux notes where they differ.

| Phase | What | Time |
|---|---|---|
| 1 | Machine prerequisites | 10 min |
| 2 | Foundry Local, model pulled and verified | 20 min, mostly download |
| 3 | Demo 2 smoke test | 10 min |
| 4 | Demo 1 locally | 15 min |
| 5 | Azure DevOps org, project, repo | 20 min |
| 6 | Self-hosted agent | 20 min |
| 7 | Pipeline, permissions, branch policy, PR | 30 min |

Phases 6 and 7 are the long poles. Everything before them is fast.

---

## Phase 1: machine prerequisites

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

**Checkpoint**

```bash
git --version          # any 2.x
python3 --version      # 3.9+
df -h /                # want 20 GB free
```

The repo is public, so cloning needs no GitHub auth. You only need `gh` if you
intend to push from this machine.

---

## Phase 2: Foundry Local

```bash
brew tap microsoft/foundrylocal
brew install foundrylocal
foundry --version
```

Linux: download the release asset from
`github.com/microsoft/Foundry-Local/releases` and put the binary on PATH.

See what is actually in the catalogue rather than trusting an alias from a doc:

```bash
foundry model list
foundry model download phi-4-mini
foundry model run phi-4-mini          # ask it something, then Ctrl-D
foundry service status                # NOTE THE PORT. It is not always 5273
```

**Get the two values everything else depends on:**

```bash
export FOUNDRY_URL=http://localhost:PORT/v1
export FOUNDRY_MODEL=$(curl -s $FOUNDRY_URL/models | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")
echo "$FOUNDRY_MODEL"
```

The full id carries a version suffix, e.g. `Phi-4-mini-instruct-generic-gpu:5`.
Use it verbatim. The CLI takes aliases, the API does not.

Put both exports in `~/.zshrc` so you are not retyping them under pressure.

**Checkpoint**

```bash
curl -s $FOUNDRY_URL/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"$FOUNDRY_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"reply with ok\"}],\"max_tokens\":10}" \
  | python3 -m json.tool
```

**Then the same thing with wifi off.** That is the 0:10 demo beat, so prove it
on this machine before Friday.

---

## Phase 3: Demo 2

Self-contained. No Azure DevOps, nothing extra to install.

```bash
git clone https://github.com/venura9/experts-live-2026.git
cd experts-live-2026/demo2-risk-sentinel
```

```bash
# without a model at all
python3 run.py reset
python3 run.py --mock doctor                                    # READY
python3 run.py --mock classify --file scenarios/03_exchange_incident.txt
python3 run.py --mock bot --cycles 5 --interval 0 --no-web      # placed > 0

# against your real model
python3 run.py reset
python3 run.py doctor                                           # READY, not DEGRADED
python3 run.py classify --file scenarios/03_exchange_incident.txt
```

**Checkpoint, the one that matters:**

```bash
python3 run.py reset
FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web
# MUST read: placed 0
python3 run.py reset
```

If that places even one order the demo proves the opposite of the talk. Stop.

**Dashboard:**

```bash
python3 run.py --mock classify --file scenarios/01_routine.txt
python3 run.py --mock bot --cycles 8 --interval 2 --hold
# open http://127.0.0.1:8099, then Ctrl-C
```

**Staleness.** `--max-age` defaults to 60 seconds, so a single classification
goes STALE after a minute and the gate blocks. That is correct, and on stage it
is an egg timer. Run the live demo with headroom:

```bash
python3 run.py bot --cycles 20 --interval 2 --max-age 300 --hold
```

Then demonstrate staleness deliberately as its own beat:

```bash
python3 run.py bot --cycles 3 --interval 0 --max-age 0 --no-web
```

---

## Phase 4: Demo 1, locally

Azure DevOps checks out **one** repo per pipeline, so the reviewer must live
beside the code it reviews. That means a second repo.

```bash
TALK=~/experts-live-2026
mkdir -p ~/order-api
cd ~/order-api || exit 1
[ -d .git ] && echo "STOP: already a repo" || git init -b main

git config user.email "you@example.com"
git config user.name "Your Name"
echo "# Order API" > README.md
git add -A && git commit -m "init"

git checkout -b demo/ai-review
python3 "$TALK/demo1-ado-review/seed/seed_flaws.py" --dest .

cp -r "$TALK/demo1-ado-review/scripts" .
cp -r "$TALK/demo1-ado-review/prompts" .
cp "$TALK/demo1-ado-review/review-paths.txt" .
cp "$TALK/demo1-ado-review/hosted-requirements.txt" .
cp "$TALK/demo1-ado-review/azure-pipelines.yml" .
cp "$TALK/demo1-ado-review/azure-pipelines-hosted.yml" .

git add -A && git commit -m "add order api"
```

`scripts/` and `prompts/` must stay siblings. The reviewer resolves its prompt
as `../prompts/mulesoft-review.md` relative to itself.

**Checkpoint**

```bash
python3 scripts/ai_review.py --dry-run --diff-base main
time python3 scripts/ai_review.py --dry-run --diff-base main
```

Findings should print for `global-config.xml`, `order-api.xml` and `pom.xml`.
Note how many of the five it catches; the scorecard slide claims all five. Under
90 seconds total, or pick a smaller model.

Then wifi off, run it again, findings still print.

**The SDK version:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install foundry-local-sdk openai
python3 scripts/ai_review_sdk.py --dry-run --diff-base main
```

Use a venv. The SDK pins its own onnxruntime.

Note the two variables are different on purpose:

| Variable | Used by | Value |
|---|---|---|
| `FOUNDRY_MODEL` | `ai_review.py` | full id from `/v1/models`, version suffix included |
| `FOUNDRY_ALIAS` | `ai_review_sdk.py` | short alias like `phi-4-mini` |

`manager.catalog.get_model()` takes an alias and resolves the variant itself. A
full versioned id fails.

---

## Phase 5: Azure DevOps org, project, repo

1. Sign in at `dev.azure.com`. Create an organisation if you do not have one.
2. New project. Name it `order-api`. **Private.** Git for version control.
3. Repos, then Files. It offers an empty repo with a clone URL. Copy it.

Push your local repo:

```bash
cd ~/order-api
git remote add origin https://dev.azure.com/<org>/<project>/_git/order-api
git push -u origin main
git push -u origin demo/ai-review
```

Push `main` first. The branch policy in Phase 7 attaches to `main`, and it must
exist before the policy can.

**Checkpoint:** both branches visible in Repos > Branches.

---

## Phase 6: self-hosted agent

Skip this phase entirely if you are demoing `azure-pipelines-hosted.yml`
instead. Microsoft-hosted agents need no setup.

**Create the pool.** Project settings > Agent pools > Add pool > Self-hosted.
Name it `local-ai`. Tick "Grant access permission to all pipelines".

**Create a PAT.** User settings (top right) > Personal access tokens > New.
Scope: **Agent Pools (read, manage)**. Copy it, you cannot see it again.

**Install the agent** on the machine that has Foundry Local:

```bash
mkdir -p ~/azagent && cd ~/azagent
# download the macOS or Linux agent from:
# Project settings > Agent pools > local-ai > New agent
tar zxvf ~/Downloads/vsts-agent-osx-arm64-*.tar.gz
./config.sh
```

It asks for:

- server URL: `https://dev.azure.com/<org>`
- authentication type: PAT
- the PAT you just created
- agent pool: `local-ai`
- agent name: accept the default
- work folder: accept the default

Run it in the foreground so you can see what it is doing:

```bash
./run.sh
```

Leave that terminal open. `./svc.sh install && ./svc.sh start` runs it as a
service instead, but for a demo the foreground output is useful on screen.

**Checkpoint:** Project settings > Agent pools > `local-ai` > Agents shows
green and Online.

**The agent inherits its own environment, not your shell.** Either export
`FOUNDRY_URL` and `FOUNDRY_MODEL` before starting the agent, or set them as
pipeline variables in Phase 7.

---

## Phase 7: pipeline, permissions, branch policy, PR

**Create the pipeline.** Pipelines > New pipeline > Azure Repos Git > pick
`order-api` > Existing Azure Pipelines YAML file > `/azure-pipelines.yml`.
**Save, do not Run.**

**Grant the comment permission. This is the step that fails silently.**

Project settings > Repositories > `order-api` > Security. In the user dropdown
find `<Project Name> Build Service (<org>)`. Set **Contribute to pull requests**
to **Allow**.

Without it the review runs, finds everything, and the thread POST returns 203.
It fails at the last step of your longest demo.

**Add the branch policy. The `pr:` trigger does not work on Azure Repos.**

Repos > Branches > `main` > ... > Branch policies > Build Validation > Add.

- Build pipeline: the one you just created
- Path filter: blank
- Trigger: Automatic
- Policy requirement: **Required**

**Open the PR.** Repos > Pull requests > New. Source `demo/ai-review`, target
`main`. Creating it queues the build automatically.

**Checkpoint:** comment threads appear on the PR, the build fails on a blocker,
and the merge button is blocked by policy.

---

## Pre-flight, the morning of

```bash
foundry --version
foundry service status                 # note the port
curl -s $FOUNDRY_URL/models            # confirm the full id

cd ~/experts-live-2026/demo2-risk-sentinel
python3 run.py reset
python3 run.py doctor                                            # READY
FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web   # placed 0
python3 run.py reset

cd ~/order-api
python3 scripts/ai_review.py --dry-run --diff-base main          # findings print
```

Plus: agent green in `local-ai`, PR fresh with the pipeline not yet run against
the latest commit, terminal at 18pt or larger, browser at 125%, and screen
recordings of both demos on local disk.

---

## Known gaps

- Nothing in this file has been run end to end on a clean machine. Trust your
  terminal over this document, and `foundry --help` over both.
- `FOUNDRY_LOCAL_CACHE_DIR` in `azure-pipelines-hosted.yml` is an educated guess
  at the SDK's cache variable. Verify before relying on the cache step.
- Model aliases move between releases. `foundry model list` is the authority.
