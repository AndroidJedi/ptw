# Result bridge operations

Deploy the worker image before the API image. The new worker understands the
old queue schema; API startup then applies additive migrations before admitting
new bounded PTW modes.

Verify `/internal/llm/structured/capabilities` through the authenticated
application canary. It must report exactly `product_brief`,
`product_brief_revision`, `studio_creative_generation`,
`studio_edit_learning`, and `content_non_human_graphic_generation`.
The media canary must cover both a fresh text-free graphic and one
digest-mapped PNG enhancement.

Before and after a PTW application reset, compare row counts for every platform
table. Do not drop or recreate this database. On rollback, restore the matching
API and worker image tag together. Remove obsolete `git-watcher` and
`git-credential-agent` containers after the Result-only services are healthy.

The worker needs the root-owned Codex package and authentication mounts. It has
no Git credentials, repository workspace, owner attachments, or Telegram send
path. Generated graphic bytes live in the external private assets volume and
are returned only through the authenticated digest-checked endpoint.

`content_non_human_graphic_generation` accepts either no attachment or exactly
one 512–2048px square PNG reference up to 8 MiB. API and worker both verify MIME,
header dimensions, SHA-256, and request size. The worker writes it only to its
ephemeral directory, attaches it to the fresh Codex call, omits its base64 from
the prompt, records the reference digest/transport, and removes the temporary
file when the call ends.
