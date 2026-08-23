# Irreversible PTW v2 reset

The owner selected a backup-free reset. It is intentionally irreversible and
must be invoked only with:

```sh
scripts/reset_ptw.sh --confirm 'RESET PTW PRODUCTION' --release-tag RELEASE_TAG
```

The allowlist is exact: stop PTW application services; drop/recreate only
`ptw_commander.public`; clear only generated Landing output under the owner
volume; apply the clean baseline; start Commander, Positioning, and Owner
Gateway; verify zero domain/graph counts and retired table absence; compare
exact table counts captured from the independent platform database; remove the
retired Idea container only after v2 readiness.

The script must not drop, migrate, seed, truncate, or rewrite the platform
database; clear platform workspaces; touch Git/credentials; delete the database
or owner-control volumes; use `latest`; or proceed without all three matching
images. Production is deliberately empty after reset.
