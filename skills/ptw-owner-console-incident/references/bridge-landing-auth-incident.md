# Bridge, Landing, and ChatGPT authorization incident

Use this runbook when production combines any of these symptoms:

- a Brief GET succeeds with HTTP 200 but the entity has `status: failed`, no
  document, and `structured bridge request N failed`;
- Landing is absent from the web navigation;
- ChatGPT Authorization says authorization is required but Refresh appears to
  do nothing.

## Interpret the evidence

- The number in `structured bridge request N failed` is the platform bridge job
  ID, not an HTTP status. Correlate it with the platform `jobs` row and worker
  execution without printing prompts, tokens, or credentials.
- HTTP 200 on the Brief GET proves only that the failed entity can be read. It
  does not prove generation readiness.
- A missing Landing marker in the live hashed bundle plus missing Landing schema
  tables means the Landing release was never deployed. Treat that as a release
  mismatch, not a browser-cache diagnosis.
- Matching human-readable image tags are not proof of matching content. Inspect
  immutable image IDs, both Git revisions, live bridge capabilities, and the
  deployed hashed web bundle.
- Multiple simultaneous symptoms usually indicate a mixed or stale compatible
  set. Keep Commander, Validation, Owner Gateway, platform API/worker/auth,
  schema migrations, and Firebase Hosting on one reviewed release contract.

## Diagnose ChatGPT authorization

1. Inspect only credential-file presence, ownership, permissions, and mtime.
   Never print or copy its contents.
2. Do not trust `codex login status` alone. Require a bounded, token-safe
   `codex exec --ephemeral` working test whose only accepted output is the fixed
   sentinel expected by the auth service.
3. Inspect the running `codex-auth` image ID, health, and network attachments.
   It needs `backend` for the private API and `edge` for outbound OpenAI access.
4. Start refresh through the owner-facing endpoint. The durable browser contract
   is `authorizing` plus the exact official device URL and a one-time code.
5. Classify failures:
   - no URL and a quick return to `authorization_required`: check outbound DNS/
     HTTPS and that Codex received a pseudo-terminal;
   - URL present but code absent: strip ANSI CSI styling before applying the
     bounded code regex;
   - `authorized` from login status but the working test fails: treat the
     credential as stale and require a new owner-completed device flow;
   - saved credentials followed by `failed`: preserve the failure and retry the
     working test; do not claim readiness.
   - the first bridge job fails immediately with `PermissionError` after a new
     login: verify the non-root worker can read its mounted credential. Keep the
     file root-owned and grant only the dedicated worker group read access; do
     not make it world-readable or run the worker as root.
6. Success is only `status: authorized` and `test_status: passed` after the
   working model request. The owner must complete OpenAI account/workspace
   approval; automation may prepare and poll the challenge but must not replace
   that human step.

Run a small bounded retry set for the working test after credential handoff.
The first model request can fail transiently while the new login becomes usable;
if an identical isolated test passes immediately afterward, retry verification
instead of forcing another device login. Keep the final state failed when every
bounded attempt fails.

The service implementation must launch `codex login --device-auth` on a
pseudo-terminal, collect output asynchronously, remove ANSI control sequences,
return only the allowlisted URL/code, expire the flow, and verify the resulting
credential with a real bounded request. Never log raw terminal output because
future CLI versions may add sensitive fields.

Codex can recreate `auth.json` as root mode `0600` during device login. After a
successful handoff, the root auth service must publish it as root-owned mode
`0640` to the worker's dedicated numeric group. Give the auth container that
supplemental group, keep the worker non-root, and retain the worker's read-only
single-file mount. Verify readability from inside the worker before canaries.

## Repair and accept

- Patch and test the canonical local repositories. Do not edit either production
  worktree or copy credentials between the unrelated repositories.
- Build versioned Linux/amd64 images off-host. An auth-only cutover may restore
  the human login boundary before a full release, but it must change only the
  private auth container and must be followed by the complete compatible release.
- Do not reset while provider readiness or release canaries fail. After the
  owner supplies the exact reset confirmation, use the repository's serial
  publisher so canaries run before the irreversible allowlisted reset.
- Acceptance requires exact bridge modes, the Landing web marker and schema,
  `codex-auth` on backend plus edge, authorization working test passed, matching
  revisions/images, public boundary audit, clean reset counts, and healthy
  restart behavior.

For one-image enhancement, current Codex CLI JSON may show only outer
`command_execution` events and omit the nested imagegen argument object. Do not
fail solely because `num_last_images_to_include` is absent from that stream, and
do not claim evidence that the runtime cannot observe. Require the observable
boundary instead: exact digest/MIME/dimensions for one reference, private
materialization, one explicit CLI `--image` attachment, digest-only prompt
mapping, exactly one bounded square output PNG, an output digest different from
the reference, and recorded evidence
`validated_cli_attachment_and_distinct_output`. Base64 reference bytes must
never enter the prompt or persisted metadata.

Do not store one-time codes, tokens, credential contents, incident-specific job
IDs, IP addresses, release hashes, or personal identifiers in this skill.
