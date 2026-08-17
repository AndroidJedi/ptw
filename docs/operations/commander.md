# Commander runtime operations

Status: web-only runtime
Updated: 2026-08-17

Run the deterministic learning-domain demonstration and unit tests from the
repository root:

```sh
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
```

The executable production composition is `docker-compose.commander.yml`. It
contains the Commander database/migrator, domain API, outbox worker, ad worker,
Owner Gateway, and reset-independent control storage. Idea Evolution runs from
`docker-compose.idea-generation.yml` on the shared platform backend network.

PostgreSQL owns domain entities, relationship edges, feedback, jobs, and
projections. Git owns migrations, policies, prompts, and canonical docs.
Entity/edge changes and outbox records commit in one transaction. Generated
files are immutable and addressed by SHA-256 digest.

## Runtime controls

- Normal owner actions use Firebase-authenticated `/api/v1/*` endpoints.
- Telegram is limited to notifications plus `/help`, `/status`, and `/stop`.
- Emergency stop is durable and checked before generation or execution side
  effects; only the web System view resumes all runtimes.
- Plan mode is read-only. Execute requires the immutable plan digest, and a
  destructive plan also requires exact owner confirmation.
- The root broker is a separate break-glass systemd service and never exposes
  credentials or PTY transcripts to PostgreSQL.

## Image generation

The ten-context post workflow uses A01–A10, `gpt-image-2` high-quality source
images, and deterministic 1080×1350 final rendering. `commander-ad-worker` owns
provider calls so outbox delivery is not blocked. Missing provider readiness
preserves the batch and creates actionable job/issue state; there is no silent
model fallback.

See [`owner-control-plane.md`](owner-control-plane.md) for authentication,
Plan/Execute, root terminal, deployment, and production acceptance. See
[`disaster-recovery.md`](disaster-recovery.md) for the irreversible reset boundary.
