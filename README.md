# PTW validation workspace

PTW is an owner-operated validation app with two focused destinations:

```text
one idea → one Product Brief → owner correction or approval
standalone Universal Studio → saved configuration → immutable approved version
```

The former Social posts/Result subsystem, candidate generator, review workflow,
exports, notifications, learning records, static-social recipes, and SKYNET
experiment tree are removed. There is no publishing, campaign, traffic, UTM,
analytics, or automatic optimization surface.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
npm --prefix apps/commander-web ci
scripts/run_local_studio.sh
```

Open `http://127.0.0.1:5173/?e2e=1`. Product Brief records are append-only under
`.local/owner-briefs`; Universal Studio state remains under
`.local/studio-workspace`. An authenticated Codex CLI is required for Brief
generation. Pexels is used only by Studio asset search. The launcher binds to
`127.0.0.1` and does not deploy or publish.

To irreversibly clear only local Brief data after stopping the app:

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
