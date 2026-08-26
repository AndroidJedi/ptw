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

There is no legacy five-Ad batch, separate Ads or Studio workspace, Landing,
Admin job system, publishing, campaign, traffic, UTM, analytics, or automatic
optimization surface. Removed systems remain only in Git history.

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
