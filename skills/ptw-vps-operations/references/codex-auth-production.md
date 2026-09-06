# Production Codex authorization recovery

This is a semi-automated boundary: PTW may start the device flow, expose only the
official URL and one-time code, poll it, and run the post-login working test. The
owner must complete OpenAI authentication and workspace approval.

## Read-only triage

- Hold no maintenance lock for ordinary status inspection. Identify the exact
  running auth image ID and health without rendering environment values.
- Confirm the private service has both `backend` and `edge` network attachments.
- Confirm the persisted credential is root-owned and not world-readable, then
  test only that the non-root platform worker can read its read-only mounted
  copy. Do not print the file or loosen it to mode `0644`.
- Query authorization through the Owner Gateway/auth bridge using its existing
  runtime environment. Print only `status`, `test_status`, `authorization_url`,
  and `device_code`; never print headers, environment, raw CLI output, or the
  persisted auth JSON.
- `codex login status` is advisory. The production readiness result comes from
  the bounded working test.

## Safe repair sequence

1. Synchronize and test the canonical local main and platform branches without
   overwriting uncommitted work.
2. Ensure the platform auth launcher uses a pseudo-terminal, removes ANSI CSI
   styling before parsing, and keeps only an allowlisted OpenAI device URL and
   bounded code. Ensure Compose attaches `codex-auth` to `[backend, edge]` and
   gives it the worker's dedicated supplemental group so it can publish the
   root-owned credential as group-readable mode `0640` after Codex rewrites it.
3. Run the platform auth/unit suite and render Compose with disposable values.
4. Build an immutable non-`latest` Linux/amd64 release image off-host.
5. In one nonblocking maintenance lock, load the image and recreate only
   `codex-auth` with `--no-deps --no-build`. Verify its exact image ID and health.
   If the installed production Compose predates the durable edge declaration,
   connecting the recreated container to the existing edge network is a
   temporary recovery step only; the subsequent platform revision must make it
   declarative.
6. Start refresh once, confirm both URL and code appear, and wait for the owner.
   Do not start competing device flows. Require `authorized` plus a passed
   working test before provider canaries. The auth service should retry only the
   bounded working test after a transient post-login failure; it must not launch
   another device flow automatically.
7. Promote the complete compatible image/revision set with
   `scripts/publish_ptw_release_serial.sh`. An irreversible reset still requires
   the owner's separate exact `RESET PTW PRODUCTION` confirmation and must occur
   only after all real provider canaries pass.

## Verification and stopping conditions

- Stop before reset on auth failure, missing URL/code, failed working test,
  wrong bridge modes, failed JSON/media/Pexels canary, checksum mismatch, or an
  unavailable maintenance lock.
- Diagnose fresh and enhancement media canaries separately. A current CLI may
  omit nested imagegen arguments from `--json`; accept enhancement only when the
  bridge proves one validated private CLI attachment, one valid square output,
  a distinct output digest, and the bounded evidence marker. Do not weaken this
  to output existence alone or persist raw reference bytes/prompts.
- After cutover verify matching immutable images/revisions, exact capabilities,
  auth health and networks, `authorized`/`passed`, Landing schema and live bundle,
  public boundary audit, reset counts, independent platform-data preservation,
  and restart recovery.
- A temporary auth-only hotfix is not incident completion. Completion requires
  the same fix in the deployed platform revision and the full release contract.

Never store production credentials, one-time codes, host-specific secrets,
incident job IDs, or ephemeral release hashes in this skill.
