# PTW Result v1

PTW is an owner-operated content validation loop:

```text
one idea -> one approved Product Brief -> five isolated Creatives
  -> owner Approve | Regenerate all | Tune one with comment
```

Public Result generation uses only the approved Brief, a fixed server task,
the canonical Natal brand kit, approved Project/Pexels sources, and versioned
writing/template contracts. The Owner Console creates one deterministic
Instagram square post or TikTok vertical photo post; it exposes no text
profile, task field, asset upload, or brand-kit setup.
Exact offer/CTA, honest claims, real-photo policy, no synthetic people/faces,
bounded retries, deterministic integrity, immutable lineage, and owner-only
selection are mandatory. No automatic evaluation, score, rank, or final choice
exists.

There is no legacy five-Ad batch, separate Ads workspace, Landing, Admin job
system, publishing, campaign, traffic, UTM, analytics, or automatic
optimization surface. A new owner-only Universal Ad Studio lives inside the
same app and configures one fixed semantic advertising structure without
changing the normal Result journey. Removed systems remain only in Git history.

## Run the Owner app locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
npm --prefix apps/commander-web ci
scripts/run_local_studio.sh
```

Open `http://127.0.0.1:5173/?e2e=1`. Product Briefs, approved Project assets,
five-Creative Instagram review runs, exports, feedback, rules, and snapshots use
a restart-safe append-only local authority under `.local/owner-experiments`;
Universal Studio configuration and saved state remain under
`.local/studio-workspace`. An authenticated Codex CLI is required for Brief,
and CandidateV2 generation. Firebase, PostgreSQL, and production provider
credentials are not required. The script binds both servers to `127.0.0.1`,
stops the API when you press `Ctrl+C`, and does not deploy or publish anything.
The launcher automatically reads `PEXELS_API_KEY` from the ignored local file
`.local/local-studio.env` when the variable is not already exported. Keep that
file owner-readable only (`chmod 600`); approved real-photo sourcing fails
closed if the credential is absent.

To irreversibly clear only local Result review data after stopping local runs
and services:

```sh
scripts/reset_ptw_local.sh --scope owner-experiments \
  --confirm='RESET PTW LOCAL RESULT DATA'
```

The reset preserves every other `.local` store, archive, and diagnostic and
proves `.local/owner-experiments` is empty.

An explicitly separate development launcher can inspect and mutate live
Project, Brief, and Social Post data through Firebase Auth, App Check, and the
public Owner Gateway while keeping only Studio on loopback:

```sh
PTW_FIREBASE_APPCHECK_DEBUG_TOKEN=REGISTERED_TOKEN \
  scripts/run_live_social_workspace.sh \
  --confirm-live-production=LIVE_PRODUCTION_DATA
```

It displays a persistent `LIVE PRODUCTION DATA` banner and reconfirms create
and revision actions. It never gives the browser PostgreSQL, bridge, provider,
or production service credentials.

## Local verification

```sh
scripts/verify_ptw_result_schema.sh
python3 scripts/verify_content_corpus.py
python3 scripts/verify_ptw_skills.py
python3 -m unittest discover -s tests/validation_pipeline -v
python3 -m unittest discover -s tests/owner_gateway -v
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
git diff --check
```

FastAPI, Pillow, and PostgreSQL lifecycle tests run in built images or a
disposable PostgreSQL container. See [`docs/README.md`](docs/README.md) for
selective context and
[`docs/architecture/commander-current-state.md`](docs/architecture/commander-current-state.md)
for the resume point.

The production reset is backup-free, limited to the Commander-owned
application schema, and requires exact confirmation `RESET PTW PRODUCTION`.
The independent platform database and unrelated local databases are preserved.
