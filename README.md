# PTW Result v1

PTW is an owner-operated content validation loop:

```text
one idea -> one approved Product Brief -> one-click Instagram post
  -> five isolated candidates -> three critic passes -> one final post
```

Public Result generation uses only the approved Brief, a fixed server task,
the canonical Natal brand kit, approved Project/Pexels sources, and versioned
writing/template contracts. The Owner Console creates only a deterministic
Instagram square post; it exposes no text profile, task field, asset upload, or
brand-kit setup.
Exact offer/CTA, honest claims, real-photo policy, no synthetic people/faces,
bounded retries, immutable lineage, and fail-closed final selection are
mandatory.

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

Open `http://127.0.0.1:5173/?e2e=1`. Product Briefs and Instagram post use one
clearly labeled deterministic local demonstration journey so every visible
destination works without Firebase, PostgreSQL, or provider credentials.
Provider-backed Brief correction/generation and Result generation are disabled
in this standalone mode; the Universal Ad Studio is fully writable. Its reusable
configuration, fixed-slot assets, source provenance, rendered PNGs, and
immutable versions stay under `.local/studio-workspace`. The script binds both
servers to `127.0.0.1`, stops the API when you press `Ctrl+C`, and does not
deploy anything. Set `PEXELS_API_KEY` locally to enable background and
isolated-object sourcing.

## Local verification

```sh
scripts/verify_ptw_result_schema.sh
python3 scripts/verify_content_corpus.py
python3 scripts/verify_ptw_skills.py
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
