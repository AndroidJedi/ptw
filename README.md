# PTW — Simplified Validation Phase 1

PTW is an owner-operated validation loop:

```text
one raw idea → one Product Brief → owner approval → five Ad Creatives
```

Stage 1 infers Ukrainian or English, chooses one marketer-led hypothesis, and
always includes a strong low-friction offer that the owner can honor. It does
not run market research, SEO, YouTube, evidence reports, AEO, or messaging
frameworks.

Stage 2 receives only the approved Product Brief and makes one five-creative
batch in fixed emotional, practical, curiosity, authority, and problem-first
angles. Pexels supplies real photographs; Pillow renders deterministic
1080×1080 JPEGs with hook, offer, and CTA. PostgreSQL stores exact image bytes,
digests, source attribution, UUID lineage, feedback, and append-only weights.

Landing is inactive and appears only as `Stage 3 pending`. The three Natal
template families and source assets stay preserved for a later simplified
conversion checkpoint. No publishing, traffic, campaigns, UTMs, analytics, or
conversion tracking exists in this release.

Firebase Auth and App Check protect the React Owner Console. Owner Gateway is
the only normal instruction channel. The independent platform repository owns
the authenticated structured LLM bridge; it has unrelated Git/database history.

## Local verification

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 -m unittest tests.owner_gateway.test_auth tests.owner_gateway.test_control_store tests.owner_gateway.test_root_broker -v
python3 -m unittest tests.commander.test_telegram_boundary -v
python3 -m commander.demo --output-dir .local/commander-demo
npm --prefix apps/commander-web run check
scripts/verify_ptw_v2_schema.sh
python3 scripts/verify_ptw_skills.py
git diff --check
```

Pillow and FastAPI runtime tests run in the built Validation and Owner Gateway
images. Landing-specific suites are deliberately excluded from this milestone.

Use [`docs/README.md`](docs/README.md) for selective context and
[`docs/architecture/commander-current-state.md`](docs/architecture/commander-current-state.md)
for the resume point. Production reset is irreversible, backup-free, limited
to `ptw_commander.public`, and requires the exact phrase
`RESET PTW PRODUCTION` immediately before cutover.
