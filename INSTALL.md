# Install and platform support

Verified against the docs and the CLI release page on 29 July 2026. Foundry
Local moves fast, so re-check `foundry --version` and the release page the
morning of the talk.



## Platform support

Foundry Local reached general availability on 9 April 2026, having been announced
in public preview at Build on 19 May 2025.

| Platform | Supported | Acceleration | Notes |
|---|---|---|---|
| Windows 10/11 x64, ARM64 | Yes | Windows ML, DirectML (GPU), QNN (Qualcomm NPU), OpenVINO (Intel), CPU | Execution provider plugins arrive via the OS, so no driver wrangling for end users |
| Windows Server 2025 | Yes | as above | |
| macOS, Apple Silicon | Yes | Metal GPU via CoreML | M1 and later. Your Mac Mini M4 is a first-class target |
| macOS, Intel | No | | Apple Silicon only |
| Linux x64 | Yes | CPU and CUDA | Added at GA. Not the NPU and iGPU breadth Windows gets via Windows ML, so say so before someone asks |
| Linux ARM64 | Yes | CPU only | A `linux-arm64` CLI asset ships. A Pi 5 is technically in scope but slow enough that you should not demo it |
| iOS, Android | Not for the runtime | | Reach a host over the network instead |

Two nuances worth saying out loud, because someone will ask:

1. **It is not a server inference stack.** Microsoft's own FAQ says Foundry
   Local is optimised for a single user on one device, and points at vLLM or
   Triton for concurrent multi-user serving. This matters for Demo 1: one build
   agent, one review at a time. Scale by adding agents, not by adding load.
2. **The CLI and the runtime version separately.** The runtime is GA; the CLI
   is still a preview asset on the GitHub releases page, and the whole command
   surface was rewritten in June 2026. Pin the version you rehearsed with.

## Prerequisites

- 8 GB RAM minimum, 16 GB recommended
- 3 GB free disk minimum, 15 GB recommended once you keep a few models
- Internet for the first model download only. After that it runs fully offline,
  which is the reveal in both demos.

## macOS

```bash
brew tap microsoft/foundrylocal
brew install foundrylocal
foundry --version
```

Uninstall if you need to reset a broken install mid-conference:

```bash
brew rm foundrylocal && brew untap microsoft/foundrylocal && brew cleanup --scrub
```

## Linux x64

Download the asset for your platform from the GitHub releases page
(`github.com/microsoft/Foundry-Local/releases`), then put the binary on PATH:

```bash
tar -xzf foundry-local-linux-x64.tar.gz
sudo install -m755 foundry /usr/local/bin/foundry
foundry --version
foundry service start
foundry service status
```

Acceleration on Linux is CPU or CUDA only. On a CPU-only ADO agent, expect a
small model at roughly 15 to 25 tokens per second, which is fine for a PR review
that runs in the background and terrible for anything interactive. Size your
demo accordingly, or run the agent on the Mac.

## First run, either platform

```bash
foundry service status                         # note the PORT
foundry model list                             # catalog
foundry model download phi-4-mini              # or another alias from the list
foundry model run phi-4-mini                   # interactive, good for the CLI tour
curl http://localhost:PORT/v1/models           # the full model ID lives here
```

Most commands take `--output json`, which is worth knowing if you script
anything on stage.

**Model aliases move.** The scripts in this repo default to `phi-4-mini` via
`FOUNDRY_MODEL`. Run `foundry model list` on your actual machine, pick what is
there, and export the full ID from `/v1/models` before you present. Do not trust
an alias you read in a document, including this one.

## SDKs

Native SDKs ship for C#, JavaScript, Python and Rust. There is no Go SDK, which
is worth a line on the slide for your usual audience: you call the
OpenAI-compatible endpoint from Go and it works fine, you just do not get the
in-process runtime.

```bash
pip install foundry-local-sdk            # macOS, Linux
pip install foundry-local-sdk-winml      # Windows, with hardware acceleration
```

Watch out: the PyPI package named `foundry-local` (no `-sdk`) is an unrelated
third-party package. Both demos in this repo avoid the SDK entirely and use the
optional local web server over plain HTTP, so there is nothing to install and
nothing to break on venue wifi.

## Two ways to call it

| | In-process SDK | Local web server |
|---|---|---|
| Shape | `FoundryLocalManager` in your app | OpenAI `/v1/chat/completions` |
| Best for | Shipping an app to end users | Pipelines, scripts, LangChain, demos |
| Used by | Not in these demos | Both demos here |

The web server is what makes the portability claim concrete: the same code
points at Azure AI Foundry by changing one environment variable. Show that on
stage. Change `FOUNDRY_URL`, rerun, identical output.

## Pre-flight, 20 minutes before you speak

```bash
foundry --version
foundry service status                                          # service healthy
foundry model load <alias>                              # avoid a cold start on stage
curl -s http://localhost:PORT/v1/models                 # copy the exact full ID
export FOUNDRY_MODEL=<full-model-id>
export FOUNDRY_URL=http://localhost:PORT/v1
cd demo2-risk-sentinel && python3 run.py doctor         # prints READY
cd ../demo1-ado-review && python3 scripts/ai_review.py --dry-run --diff-base origin/main
python3 bench.py                                        # your own numbers for the stats slide
```

Port 5273 was the old service default and the scripts still fall back to it.
Read the real port from `foundry service status` and export `FOUNDRY_URL` rather than
relying on that default.
