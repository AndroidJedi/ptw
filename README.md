# PTW validation workspace

PTW is an owner-operated validation app with two destinations:

```text
one idea → one Product Brief → owner template choice and approval
approved Brief → project creative → Studio AI draft → Save/Approve learning
```

The common Studio catalog provides `universal_ad` and `phone_metrics`.
Creatives, edit checkpoints, skills, assets, and immutable versions are
Project-scoped. The former Social Post automation, review/export/publication
workflow, candidate/critic modes, singleton Studio, and compatibility migrations
are absent.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
npm --prefix apps/commander-web ci
scripts/run_local_studio.sh
```

Open `http://127.0.0.1:5173/?e2e=1`. Append-only Brief/creative metadata is
stored below `.local/owner-briefs`; per-creative renderer files are below
`.local/studio-workspace/creatives`. An authenticated Codex CLI provides local
Brief, Studio composition/learning, phone-image, and Tune work. Pexels provides
provenance-retained photographs. The launcher binds to `127.0.0.1` and never
deploys or publishes.

To irreversibly clear only local Brief/creative metadata after stopping the app:

```sh
scripts/reset_ptw_local.sh --scope owner-briefs \
  --confirm='RESET PTW LOCAL BRIEF DATA'
```

## Verify

```sh
scripts/verify_ptw_brief_schema.sh
python3 scripts/verify_ptw_skills.py
python3 -m unittest discover -s tests/validation_pipeline -v
python3 -m unittest discover -s tests/owner_gateway -v
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
git diff --check
```

See [`docs/README.md`](docs/README.md) for selective context. Production reset
remains confirmation-gated and preserves the unrelated platform database.
