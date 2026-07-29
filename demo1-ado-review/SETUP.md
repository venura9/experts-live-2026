# Setting up the demo repo

Azure DevOps checks out **one** repo per pipeline. The reviewer has to live in
the same repo as the code it reviews, so you build a second repo that combines
the MuleSoft app with the review tooling from this one.

## One command

From anywhere, with this repo cloned:

```bash
TALK=~/experts-live-2026          # wherever you cloned it
mkdir -p ~/order-api && cd ~/order-api

git init -b main
echo "# Order API" > README.md
git add -A && git commit -m "init"

git checkout -b demo/ai-review

# the MuleSoft app
python3 "$TALK/demo1-ado-review/seed/seed_flaws.py" --dest .

# the review tooling, beside it
cp -r "$TALK/demo1-ado-review/scripts" .
cp -r "$TALK/demo1-ado-review/prompts" .
cp "$TALK/demo1-ado-review/review-paths.txt" .
cp "$TALK/demo1-ado-review/hosted-requirements.txt" .
cp "$TALK/demo1-ado-review/azure-pipelines.yml" .
cp "$TALK/demo1-ado-review/azure-pipelines-hosted.yml" .

git add -A && git commit -m "add order api"
```

## The layout both pipelines expect

```
order-api/
  src/main/mule/global-config.xml      generated
  src/main/mule/order-api.xml          generated
  src/main/resources/config/dev.yaml   generated
  src/main/resources/api/order-api.raml generated
  pom.xml                              generated
  scripts/ai_review.py                 copied
  scripts/ai_review_sdk.py             copied
  prompts/mulesoft-review.md           copied
  review-paths.txt                     copied
  hosted-requirements.txt              copied
  azure-pipelines.yml                  copied
  azure-pipelines-hosted.yml           copied
```

Both pipelines run from the repo root and call `scripts/ai_review*.py`. Neither
sets a `workingDirectory`. If you nest the tooling in a subfolder, both break.

`scripts/` and `prompts/` must stay siblings: the reviewer resolves its prompt
as `../prompts/mulesoft-review.md` relative to its own location.

## Test before you touch Azure DevOps

```bash
cd ~/order-api
python3 scripts/ai_review.py --dry-run --diff-base main
```

Findings should print for `global-config.xml`, `order-api.xml` and `pom.xml`.
If that works locally, the pipeline is only wiring.
