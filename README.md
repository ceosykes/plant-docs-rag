# RAG build templates

Everything that stays the same between RAG builds, in one folder. Copy it into a new
project folder, add the corpus and the scenario, and start.

## Starting a project

```bash
cp -R ~/Downloads/rag-templates ~/Downloads/<project-name>
cd ~/Downloads/<project-name>
cp .env.example .env            # fill in the keys
mkdir -p data/raw               # drop the corpus here
```

Then write `SCENARIO.md`, the case as it was handed to you. Then open `START_HERE.md`,
fill in the three bracketed sections, and paste it into a fresh Claude Code chat.

The agent drafts the dictation from the scenario and stops. You correct it, then it
builds. When `config.py` exists, it writes `deploy.env` so the scripts know the variable
names and routes. At the end, `./deploy.sh`.

## What is in here

Prompts the agent reads, in `prompts/`:

    FDE_PERSONA.md               who the agent is, how it talks, how it writes code
    HUMANIZER.md                 how prose reads
    RAG_BUILD_PROMPT.md          the phases, the gates, the feature menu, what is never cut
    INPUT_TEMPLATE.md            the blank dictation block the build prompt expects
    EXAMPLE_INPUT_freddie.md     a filled-in dictation, for reference
    DISCOVERY_MASTER_PROMPT.md   the eight questions to ask a client before any code
    SUMMARIZE_PROMPT.md          raw discovery notes to two paragraphs
    SOLUTION_MASTER_PROMPT.md    two paragraphs to a build order
    CLIENT_PERSONA_PROMPT.md     practice discovery against a role-played stakeholder

Files you paste or fill in:

    START_HERE.md        the first message to the agent. Three bracketed sections to fill.
    .env.example         the standard keys. Copy to .env.
    deploy.env.example   per-project names for the scripts. Copy to deploy.env.

Scripts and runbooks:

    deploy.sh            GitHub + Railway + Vercel, one command, verified at the end
    finish.sh            second half of a deploy whose Railway build already landed
    run_local.sh         API and front end on this machine
    DEPLOY_NOTES.md      what the scripts do by hand, and every caveat that cost a deploy
    TOOLS.md             the stack and why each piece is in it
    buildview.py         live dashboard of the build: python3 buildview.py . 8099
    .gitignore           secrets, built state, and anything that maps the guardrails
    .dockerignore        the image gets the API and the corpus. Nothing else.

## The order of a full engagement

Discovery, then summary, then build. The first two are optional when the scenario
arrives written.

1. `CLIENT_PERSONA_PROMPT.md` to practise, or `DISCOVERY_MASTER_PROMPT.md` with a real
   client. Twelve minutes, spoken.
2. `SUMMARIZE_PROMPT.md` turns the notes into the problem paragraph and the solution
   paragraph.
3. Those two paragraphs become WHAT I SAW, THE PROBLEM and WHAT WE BUILD in the
   dictation. `SOLUTION_MASTER_PROMPT.md` is the longer form when the build needs a
   written order before it starts.
4. `START_HERE.md`, then the build prompt runs the phases.

## What the scripts assume

A `Dockerfile` at the root that runs ingest during the build. A Vite front end in `web/`.
A FastAPI app that reads its port, its allowed origins and its internal token from the
environment, with `/health` returning 200 and the docs routes disabled. Entry points in
module form. If the build prompt was followed, all of that is already true.

## Keeping this folder current

When a build teaches something, it goes in one of three places. A new rule for the agent
goes in the build prompt or the persona. A new deploy caveat goes in `DEPLOY_NOTES.md`
and, if a script can check it, in `deploy.sh`. A new measured fact about a tool goes in
`TOOLS.md`. Nothing project-specific comes back here.
