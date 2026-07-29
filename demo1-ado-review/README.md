# Demo 1: local AI peer review of MuleSoft code in Azure DevOps

A pipeline that reviews PR diffs against MuleSoft-specific rules using a model
running on the build agent itself. Source code never leaves the machine.
Findings post back as comment threads and a blocker fails the build, so branch
policy blocks the merge.

## Setup

**A1. Agent.** Install Foundry Local on the machine that will run the agent (see
`../INSTALL.md`). Register a self-hosted agent in a pool named `local-ai`.

**A2. Model.** `foundry model load phi-4-mini` then `foundry model load <full-id>`.
Get the full ID from `curl localhost:PORT/v1/models`. The alias will not work in
API calls.

**A3. Repo.** Copy `azure-pipelines.yml`, `scripts/`, `prompts/` and
`review-paths.txt` into an Azure Repos repository.

**A4. Pipeline.** Create a pipeline from the existing YAML. Do not add a `pr:`
trigger, it does nothing for Azure Repos.

**A5. Branch policy.** On `main`, add Build Validation pointing at this pipeline.
This is the actual PR trigger.

**A6. Permissions.** Project Settings, Repositories, Security. Grant the build
service identity **Contribute to pull requests**. Without it, thread posting
returns 203 or 401.

**A7. Demo branch.**

```bash
git checkout -b demo/ai-review
python3 seed/seed_flaws.py
git add -A && git commit -m "add order api" && git push -u origin demo/ai-review
```

Open the PR. Branch policy queues the build. To hold it for stage time, disable
the pipeline and re-enable it live.

## Rehearsal without Azure DevOps

```bash
python3 scripts/ai_review.py --dry-run --diff-base origin/main
```

Findings print to stdout, nothing is posted. This is also your fallback if ADO
is unreachable on the day.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Reviewed, nothing at or above the threshold |
| 1 | Blocking findings, build fails, merge blocked |
| 2 | Model unreachable or output unusable. **Fails closed.** A review that did not happen is not a pass |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Request to local service failed ... 127.0.0.1:0` | `foundry service restart`, then re-read the port from `foundry service status` |
| Model not found | You used the alias. Use the full ID from `/v1/models` |
| 203 or 401 posting threads | Build service lacks Contribute to pull requests, step A6 |
| Pipeline never triggers | You relied on `pr:` in YAML. Use branch policy, step A5 |
| First inference very slow | Cold start. `foundry model load <id>` before you go on |


## Two versions of the reviewer

| Script | Dependencies | Use for |
|---|---|---|
| `scripts/ai_review.py` | stdlib only | The pipeline. Nothing to install on a locked-down agent |
| `scripts/ai_review_sdk.py` | `foundry-local-sdk`, `openai` | Your laptop. Three lines of setup instead of twenty |

Both produce identical review output. The difference is in how they find and
talk to the model:

- `ai_review.py` reads `FOUNDRY_URL` and `FOUNDRY_MODEL` from env vars and
  sends raw HTTP to the OpenAI-compatible endpoint. You start the service,
  download the model, and read the port yourself.

- `ai_review_sdk.py` initializes `FoundryLocalManager` and hands an alias to its
  catalog, which picks the best variant for your hardware, downloads if needed,
  and loads the model. The model then hands back a chat client directly, so
  there is no HTTP endpoint and no `openai` dependency at all.

On stage, show the SDK version first because it is shorter and the audience can
read it in one glance. Then show the pipeline YAML calling the stdlib version
and say why: a build agent in a locked-down network should not pip install
anything at runtime.

Install for the SDK version. Use a venv so you do not pollute system python,
and so the SDK's pinned onnxruntime cannot collide with anything else:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install 'foundry-local-sdk==1.2.3'
python3 scripts/ai_review_sdk.py --dry-run --diff-base main
```

### The two env vars are different on purpose

| Variable | Used by | Value |
|---|---|---|
| `FOUNDRY_MODEL` | `ai_review.py` | the **full** model id from `/v1/models`, version suffix included |
| `FOUNDRY_ALIAS` | `ai_review_sdk.py` | a short **alias** like `phi-4-mini` |

`manager.catalog.get_model()` takes an alias and resolves the best variant for
your hardware itself. Handing it a full versioned id fails. The SDK script
therefore ignores `FOUNDRY_MODEL` entirely and defaults to `phi-4-mini` unless
you set `FOUNDRY_ALIAS`.

The SDK script also starts Foundry Local lazily, inside `main()`. If it started
on import, `--help` would download a model.


## Two pipelines

| File | Agent | Script | The claim it supports |
|---|---|---|---|
| `azure-pipelines.yml` | self-hosted, in your network | `ai_review.py` (stdlib) | Our code never leaves our network |
| `azure-pipelines-hosted.yml` | Microsoft-hosted `ubuntu-latest` | `ai_review_sdk.py` (SDK) | We add no new vendor to our supply chain |

Both run the model on the same machine as the build. Neither sends source code
to a model vendor. They answer different restrictions, and the second is the
more common one.

If your repo is already in Azure DevOps, Microsoft is already a processor for
that code and it is already running in their cloud. Loading a model in-process
on the same agent expands the trust boundary by exactly zero: no new vendor, no
new DPA, no new egress rule, no security review. Calling a third-party AI API
from that same pipeline is a completely different proposition.

### Hosted agent limits, verified July 2026

| | |
|---|---|
| CPU | 2 cores (Standard_DS2_v2). No GPU, no NPU, CPU execution provider only |
| RAM | 7 GB total; Linux jobs run in a cgroup with 6 GB physical memory |
| Disk | 14 GB SSD, at least 10 GB free for your job |
| Job timeout | 60 min on a private repo (free tier); 360 min on a public repo or with paid parallel jobs |
| Lifetime | fresh VM per job, discarded afterwards |

Three consequences, all handled in `azure-pipelines-hosted.yml`:

1. **The model re-downloads every run** unless cached. The `Cache@2` task keyed
   on the model alias fixes this. Without it you burn several minutes of a
   60-minute budget re-fetching what you already had.
2. **Use a small model.** On two CPU cores a 3.8B model reviewing several files
   will eat the timeout. The pipeline defaults to `qwen2.5-0.5b`. Move up only
   after you have measured it on a real run.
3. **Keep the scope tight.** Path filters are not a nicety here, they are what
   keeps the job inside its timeout.

The pipeline prints `nproc`, `free -h` and `df -h` before it starts. Leave that
step in for the demo: the room sees two cores and ten gigabytes and understands
the model choice without you having to argue it.

### What to say on stage

Do not say "your code never leaves your machine" while demoing on a hosted
agent. Someone will call it, and they will be right. Say instead: **this adds no
new third party to your supply chain.** That claim is true on both deployment
models, and it is the one that gets budget approved.


## The MuleSoft app under review

There is no external MuleSoft project. `seed/seed_flaws.py` generates one, five
files and about 330 lines:

| File | What it is |
|---|---|
| `src/main/mule/global-config.xml` | Listener, downstream HTTPS request config with a truststore, DB config, secure-properties config |
| `src/main/mule/order-api.xml` | APIkit router, `getOrderFlow`, `createCustomerFlow`, a shared `globalErrorHandler`, DataWeave transforms |
| `src/main/resources/config/dev.yaml` | Environment properties |
| `src/main/resources/api/order-api.raml` | API spec, deliberately out of review scope |
| `pom.xml` | Mule 4.6 app with mule-maven-plugin, MUnit, connector dependencies |

**Nothing in the generated code is commented as a defect.** An earlier version
labelled each flaw in the XML, which would have wrecked the demo: the room would
watch the model "find" problems that were annotated two lines above.

The five defects sit inside code that otherwise looks competent, and each one is
detectable because it contradicts something the same codebase does correctly:

| # | Severity | What | Why it reads as a real finding |
|---|---|---|---|
| 1 | blocker | Literal DB password in `global-config.xml` | Every other value in that same config comes from properties, and there is a secure-properties config right above it |
| 2 | blocker | `ordersHttpListener` is `protocol="HTTP"` | The downstream request config in the same file correctly uses HTTPS with a truststore |
| 3 | major | `getOrderFlow` has no `error-handler` | The main flow and `createCustomerFlow` both have one |
| 4 | blocker | `createCustomerFlow` logs `#[payload]` at INFO | The transform immediately below shows that payload carries email, phone, date of birth and a tax file number |
| 5 | major | `common-transforms 2.1.0-SNAPSHOT` | Sits in a released `1.4.0` artifact alongside pinned connector versions |

Run `python3 seed/seed_flaws.py --list` to print that table without writing any
files. Useful the morning of the talk when you want to know what the model
should be catching.
