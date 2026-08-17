# PTW reset and recovery boundary

Status: confirmation-gated, intentionally no backup
Updated: 2026-08-17

By explicit owner decision, PTW does not create or require a backup before a
production reset. A reset is therefore irreversible. It still requires the
exact confirmation `RESET PTW PRODUCTION` and can run only through the
root-owned broker.

## Clean reset

The allowlist is deliberately narrow. Reset recreates only the `public` schema
in the Commander and platform PostgreSQL databases, clears only the Commander
asset volume, and clears these exact live directories:

- `/opt/ptw/workspaces/incoming`
- `/opt/ptw/workspaces/jobs`
- `/opt/ptw/persistent-data/runtime`

PostgreSQL volumes and roles, Git, SSH, Caddy, environment files, Firebase
credentials, and the reset-independent Owner Gateway control store remain.

```sh
cd /root/ptw
scripts/reset_ptw.sh --confirm 'RESET PTW PRODUCTION'
```

The postcondition is one active `MISSION_20M_3Y`, C01–C10 plus ten revisions,
A01–A10 plus ten revisions, one platform owner configuration, and zero ideas,
generations, reports, submissions, creatives, feedback, jobs, sessions, issues,
or executions. Generation 1 is never started by reset.

## Verification

The reset procedure was rehearsed against two disposable PostgreSQL 16
instances, including exact schema recreation and clean reseeding. Production
acceptance checks database counts immediately after the reset. There is no
restore promise after an owner-confirmed production reset.
