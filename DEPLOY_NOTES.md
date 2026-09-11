# Deploy

API to Railway, front end to Vercel. The API image builds its own index, so the
container starts ready and the first request does not pay for embedding.

`deploy.sh` does all of this in one command. This file is what it does, so you can do
any step by hand when the script dies halfway, and the caveats that have each cost a
real deploy.

## Before the first deploy

Fill in `deploy.env` from `deploy.env.example`. The names in it have to match what
`config.py` reads, or CORS and the token gate do nothing and say nothing.

Log in once: `gh auth login`, `railway login`, `vercel login`.

## Run it locally first

```bash
python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
cp .env.example .env                    # then fill in the keys
./run_local.sh                          # ingest if needed, API, front end
```

If it works nowhere but your working folder, it is not a deployable folder. Install the
pinned requirements into a brand new empty virtualenv and run from there before claiming
it ships.

## Railway, the API

1. Push the folder to GitHub. `.gitignore` keeps `.env`, `store/` and `runs/` out.
2. Railway, new project, deploy from the repo. It finds the `Dockerfile` and uses it.
3. Set the variables below. Railway injects `PORT` itself and the API reads it, so do
   not set `PORT`.
4. Settings, Networking, generate a domain. That URL is your API.

The build runs ingest, so the first deploy takes a few minutes while it parses the corpus
and downloads the embedding model. Every deploy after that repeats it, because the index
lives in the image.

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your key |
| `ANTHROPIC_WORKSPACE_ID` | only if the key is identity-linked rather than workspace-scoped |
| `LANGSMITH_TRACING` | `true` |
| `LANGSMITH_API_KEY` | your key |
| `LANGSMITH_PROJECT` | the project name |
| `<ORIGINS_VAR>` | the Vercel URL, once you have it |
| `<TOKEN_VAR>` | a generated token, or unset to keep internal routes localhost only |

## Vercel, the front end

1. Import the same repo. Set Root Directory to `web`.
2. Framework preset Vite. Build `npm run build`, output `dist`.
3. Environment variable `VITE_API_URL` set to the Railway URL, no trailing slash. It is
   a build-time variable. Vite inlines it. A runtime env is ignored.
4. Deploy, then go back to Railway and put the Vercel URL in `<ORIGINS_VAR>`.

Order matters. The front end needs the API URL, and the API needs the front end origin,
so one of them gets deployed twice. `finish.sh` does the second half when `deploy.sh`
died after the Railway build landed.

## Check it

```bash
curl https://<railway-url>/health
curl -s https://<railway-url>/docs -o /dev/null -w '%{http_code}\n'          # expect 404
curl -s https://<railway-url>/openapi.json -o /dev/null -w '%{http_code}\n'  # expect 404
```

Then the demo in the browser. Ask one thing the corpus answers and check the citation.
Ask one thing it cannot answer and check the refusal.

## Lessons already paid for

Every one of these has broken a real deploy. Check them by running them, not by reading
the code.

Entry points use the module form, `python -m package.module`. Running a script by file
path puts its own folder on the import path instead of the project root, and the imports
fail at boot.

No data path escapes the project root. Nothing reaches for a sibling folder. Every path,
port, URL and allowed origin comes from the environment with an in-project default.

The image never starts with an empty index. Either ingest runs during the image build, or
startup fails loudly with a message saying what to run.

`docs_url`, `redoc_url` and `openapi_url` are all `None`. Turning off the docs pages
while leaving the schema served is not a closed door.

A large first push fails with an RPC 400 on git's 1MB default post buffer and on HTTP/2.
`deploy.sh` sets `http.postBuffer` and `http.version HTTP/1.1` before pushing.

Vercel rejects a commit without a real `user.email`.

Vercel prints a per-deployment URL and an Aliased URL. The alias is the one a human
opens and the one that survives redeploys. Capture that one.

Vercel ships with SSO protection on, so a successful deploy can still show a login wall.
Turn it off in the project settings.

Vite cannot run from a folder whose path contains `#`. `run_local.sh` mirrors `web/` to
`/tmp` for that reason.

## What does not ship, and why

`.dockerignore` keeps these out of the image: `.env`, `store/`, `runs/`, `charts/`,
`flowchart.html`, the evals, the tuning code, fixtures, tests, prompts, and `web/`.

The charts and the flowchart are the reason. Between them they name every refusal
string, every forbidden pattern and the whole graph, which is a map for anyone who wants
to work around the guardrails. They belong in the repo for a reviewer and nowhere near a
public URL. The golden set stays out because publishing the test set invites gaming.

## Known limits, say these before anyone asks

SQLite on a container disk is ephemeral. Checkpoints and reviewer decisions reset on
every redeploy, so long term memory does not survive a deploy. The fix is the Postgres
checkpointer and a Postgres decisions table, which is the first thing this needs to be
real rather than a demo.

The index is baked into the image, so a corpus change means a rebuild. Fine at tens of
documents, wrong at thousands, where ingestion becomes a scheduled job against a
persistent store.

The internal token is compiled into the front end bundle. Anyone who views source can
read it. It stops a crawler. In production those surfaces sit behind the client's SSO.
