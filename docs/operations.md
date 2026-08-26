# Result bridge operations

Deploy the worker image before the API image. The new worker understands the
old queue schema; API startup then applies additive migrations before admitting
new Result modes.

Verify `/internal/llm/structured/capabilities` through the authenticated
application canary. It must report exactly `product_brief`,
`product_brief_revision`, `content_candidate_generation`,
`content_result_critic`, and `content_non_human_graphic_generation`.

Before and after a PTW application reset, compare row counts for every platform
table. Do not drop or recreate this database. On rollback, restore the matching
API and worker image tag together. Remove obsolete `git-watcher` and
`git-credential-agent` containers after the Result-only services are healthy.

The worker needs the root-owned Codex package and authentication mounts. It has
no Git credentials, repository workspace, owner attachments, or Telegram send
path. Generated graphic bytes live in the external private assets volume and
are returned only through the authenticated digest-checked endpoint.
