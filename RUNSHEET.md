# Run sheet: 50 minutes, two demos

**Thesis.** Restricted organisations want AI-assisted engineering but cannot send
code or operational data to a cloud endpoint. Foundry Local gives you an
OpenAI-shaped endpoint on a machine you already control. Demo one proves the
placement. Demo two proves you can give a small model real authority without
losing control of it.

| Time | Slides | Segment | Mode |
|---|---|---|---|
| 0:00 - 0:05 | 1-3 | The problem: DLP versus the AI mandate | Slides |
| 0:05 - 0:13 | 4-8 | What Foundry Local is, numbers, platforms, install | Slides + terminal |
| 0:13 - 0:31 | 10-16 | **Demo 1**: local dry-run offline, then the same review in the pipeline | Terminal + browser |
| 0:28 - 0:33 | 13-14 | Enterprise hardening, then the hinge | Slides |
| 0:33 - 0:44 | 15-18 | **Demo 2**: Risk Sentinel, halt without trade authority | Terminal + dashboard |
| 0:44 - 0:48 | 19-20 | Generalising, and where it does not fit | Slides |
| 0:48 - 0:50 | 21-23 | Decision framework, links, questions | Slides |

Deck: open `deck.html` in any browser. Arrows advance, `n` toggles speaker
notes, `t` starts the talk timer in the left rail, `b` flips the boundary
indicator to blocked when you go into aeroplane mode. No network needed, which
is the point.

## The repo is on screen three times

| Slide | Why there |
|---|---|
| 0:00 title | On screen while the room fills. Earliest possible, and the only one people have time to act on before you start talking |
| 0:10 install | The moment someone decides they want to try it. Demo 2 runs with `--mock`, so they can follow with nothing installed |
| 0:50 links | The takeaway, large. Leave it up through Q&A |

Say it out loud at 0:00, do not just leave it on screen. "Everything is already up
there, clone it now if you want to follow along." A QR nobody is told about is a
QR nobody scans.

## Demo 1 now covers two scenarios

The repo ships two pipelines against the same script, prompt and model:

- `azure-pipelines.yml`, self-hosted agent. Answers "our code cannot leave our
  network."
- `azure-pipelines-hosted.yml`, Microsoft-hosted `ubuntu-latest`. Answers "we
  cannot get another AI vendor through procurement."

Show the self-hosted one live. Show the hosted YAML on screen and say it runs
the same review with no self-hosted infrastructure at all. That is the "try it
tonight" path for anyone in the room without an agent to spare.

**Do not say "your code never leaves your machine" while pointing at the hosted
pipeline.** It is not true there. The claim that holds for both is: this adds no
new third party to your supply chain.

## Demo 1 beats, 15 minutes

Two parts. Part one proves the inference is local. Part two proves it fits a
real delivery process. Keep them separate: each proves one thing cleanly.

**Part one, on the laptop, no network.**

1. Show the PR diff. Give the room the scorecard slide and ask them to review it
   by eye. Five planted defects, none of them commented in the source.
2. `foundry service status` in a terminal beside the browser.
3. **Aeroplane mode on.** Press `b` on the deck. Then run
   `python3 scripts/ai_review_sdk.py --dry-run --diff-base main`.
4. Findings print with no network at all. Nothing to argue about: there is no
   connection for the code to have travelled over.

**Part two, wifi back on, in the pipeline.**

5. Show the queued build on the `local-ai` pool. Emphasise: that agent is this
   laptop, and the inference still runs on loopback.
6. Comments land on the PR, build fails, branch policy blocks the merge.
7. Put `azure-pipelines-hosted.yml` on screen. Same script, same model, on a
   Microsoft-hosted agent. That is the version anyone in the room can try
   tonight without standing up an agent.

**Do NOT kill the wifi during the pipeline run.** The agent long-polls
`dev.azure.com`, and dropping that connection can fail or abandon the job. The
aeroplane-mode moment belongs in part one, where nothing else depends on the
network. Earlier versions of this run sheet told you to do it mid-pipeline;
that was wrong.

## Demo 2 beats, 11 minutes

**Reset the ledger first.** `python3 run.py reset`. A ledger left over from
rehearsal will feed the gate a fresh-looking CLEAR and hide the whole point.

1. `python3 run.py classify --file scenarios/01_routine.txt`, then
   `python3 run.py bot --cycles 8 --interval 2 --hold`. Dashboard up, gate
   CLEAR, orders flowing.
2. `python3 run.py classify --file scenarios/03_exchange_incident.txt`. Model
   halts. Restart the bot: every cycle now blocks with `HALT`. Dashboard red.
3. `python3 run.py ledger` shows the audit trail: append-only, fsynced, every
   decision written before anything else happens.
4. **Kill the model.** `foundry service stop` in a second terminal while the bot
   is looping. Within one cycle the gate goes red with `UNPARSED`, and the
   placed counter stops moving. That is the beat people remember. Say: a
   control that fails open is not a control.

Beat 4 depends on the heartbeat added on 29 July 2026. Before that fix the bot
only read the ledger, so killing the model changed nothing for 15 minutes and
the demo silently kept trading. If you ever refactor the loop, re-test this beat
with `FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3`. It
must place zero orders.

## Pre-flight, day of

- [ ] `foundry --version` is the build you rehearsed with (0.10.x)
- [ ] `foundry service status` is healthy, `foundry service start`, note the port
- [ ] `foundry model load <full-id>` so there is no cold start on stage
- [ ] `curl localhost:PORT/v1/models` returns the ID you have configured
- [ ] `FOUNDRY_URL` and `FOUNDRY_MODEL` exported, not relying on the 5273 default
- [ ] `python3 bench.py` and paste the result onto the numbers slide
- [ ] ADO agent green in the pool
- [ ] Demo PR fresh, pipeline has NOT run against the latest commit
- [ ] `cd demo2-risk-sentinel && python3 run.py reset` to clear the ledger
- [ ] `python3 run.py doctor` prints READY
- [ ] fail-closed check: `FOUNDRY_URL=http://localhost:9999/v1 python3 run.py bot --cycles 3 --interval 0 --no-web` places zero orders
- [ ] `python3 run.py reset` again before you walk on stage
- [ ] Terminal font 18pt or larger, browser zoom 125 percent
- [ ] Screen recordings of both demos on local disk

## Failure fallbacks

| Fails | Do this |
|---|---|
| Model too slow on stage | `export FOUNDRY_MODEL=<smaller full ID>`, pre-cached. Confirm the alias with `foundry model list` the night before, aliases change between releases |
| ADO unreachable | `python3 scripts/ai_review.py --dry-run`, findings print to stdout |
| Foundry server will not bind | `foundry service restart`, then re-read the port |
| Model not found | You used the alias. Use the full ID from `/v1/models` |
| Sentinel model unavailable | `python3 run.py --mock bot`, yellow banner announces it honestly. `--mock` works on either side of the subcommand |
| Everything | The recordings |

## Questions you will get, and the honest answers

**"Can it serve our whole team?"** No. It is a device runtime, single user at a
time. Add agents, or use a real serving stack.

**"Isn't a small model just worse?"** Yes, at open-ended reasoning. Both demos
give it a narrow task with a schema and a hard gate. That is the design.

**"What if the model hallucinates a finding?"** In demo one a human still
reviews, the model only opens threads. In demo two an invented halt costs you a
paused bot, which is the cheap direction to be wrong in.

**"Why not Ollama or LM Studio?"** Legitimate alternatives. Foundry Local's
argument is the curated catalog, automatic execution provider selection, and a
supported path onto Windows fleets. Say this plainly, do not pretend there is no
competition.

**"Isn't this just a local server?"** Microsoft's own framing has moved. The
product is now positioned as an embedded SDK, roughly 20 MB in your app bundle,
with the OpenAI-compatible server described as optional and mainly for dev
workflows. Both demos here use the server because that is the right shape for a
pipeline script and a background risk gate. Acknowledge both shapes before
someone from Microsoft does it for you.
