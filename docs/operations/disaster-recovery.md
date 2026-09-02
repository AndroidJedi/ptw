# Irreversible PTW Product Brief reset

The backup-free clean-slate reset may run only with:

```sh
scripts/reset_ptw.sh --confirm 'RESET PTW PRODUCTION' --release-tag RELEASE_TAG
```

The exact workflow verifies matching versioned images, snapshots independent
platform counts, stops PTW services, recreates only `ptw_commander.public`,
applies only `001_ptw_brief_v1.sql`, restarts services, proves zero business
rows and no retired tables, verifies readiness and unchanged platform counts,
then removes only explicitly named retired containers.

It must not mutate the independent platform database, credentials, unrelated
local stores, or PostgreSQL volumes. Production is intentionally empty afterward.
