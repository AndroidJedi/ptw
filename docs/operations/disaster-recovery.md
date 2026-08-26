# Irreversible PTW Result reset

The owner selected a backup-free clean-slate reset. It is irreversible and may
run only with:

```sh
scripts/reset_ptw.sh --confirm 'RESET PTW PRODUCTION' --release-tag RELEASE_TAG
```

The allowlist is exact:

1. verify matching non-`latest` Commander, Validation, and Owner Gateway images;
2. snapshot table counts in the independent platform database;
3. stop PTW application services;
4. drop and recreate only `ptw_commander.public`;
5. remove the explicit obsolete `ptw_owner-control` volume if present;
6. apply only `001_ptw_result_v1.sql`;
7. start the three application services;
8. verify zero business rows, one migration, and no retired table families;
9. verify readiness and unchanged platform counts;
10. remove only explicitly named retired PTW containers.

The reset must not drop, truncate, migrate, seed, or rewrite the independent
platform database; touch unrelated local databases; clear platform workspaces;
change Git or credentials; remove active PostgreSQL data volumes; use `latest`;
or continue after a failed guard. Production is intentionally empty afterward.
