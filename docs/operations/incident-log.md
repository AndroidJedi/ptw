# PTW incident log

Updated: 2026-09-06

## 2026-09-06 — HTTP 200 masked a failed structured provider execution

**Symptom:** the project Brief list returned HTTP 200, but its persisted Brief
was failed after repeated `structured bridge request N failed` attempts. The UI
showed an internal bridge string without explaining that the successful HTTP
response represented only a successful read or how the owner could recover.

**Cause:** all containers were healthy and the auth service passed its working
test, but a benign probe using the worker's exact schema-bound Codex execution
path returned unauthorized. The worker used a single-file bind of the primary
credential; Codex atomically replaced that file after device login, leaving the
running worker pinned to its stale inode. The frontend also normalized transport
errors only partially, treated a readable failed entity separately, and omitted
the persisted Landing generation error.

**Durable fix:** centralized localized API failures into outcome, explanation,
safe next action, and bounded technical context; applied the same contract to
persisted Brief, Studio, phone-image, Landing, and Landing-learning failures;
and suppressed raw 5xx/provider details. The auth service now keeps the primary
credential root-only and publishes a separate copy through a dedicated directory
mount that remains current across atomic replacement. The production dependency
audit compares the handoff internally and runs a token-safe schema-bound worker
probe. Both incident resolver skills record the HTTP-200/failed-state and stale
single-file-mount diagnoses before any generation retry.

**Verification:** 58 web unit tests, 48 browser checks, the production web build,
10 Commander checks, Commander demo, 38 platform tests, skill validation, script
syntax, and whitespace checks pass. The public Hosting audit confirms Landing
and the actionable-error markers. Production auth reports `authorized`/`passed`;
the dedicated published credential matches the worker mount; the schema-bound
worker probe and complete dependency audit pass. One explicit retry changed the
same Brief from failed to completed: its third append-only attempt and latest
structured provider invocation are completed, with document digest, quality
gates, and completion timestamp present. No reset ran.

## 2026-09-06 — Mixed production release broke generation, Landing, and ChatGPT authorization

**Symptom:** a Brief remained readable over HTTP 200 but its persisted state was
failed with `structured bridge request N failed`; Landing was absent from the
navigation; and ChatGPT Authorization remained required while Refresh appeared
to do nothing. An earlier request to the retired Studio route also returned 404.

**Cause:** production combined stale and incompatible Commander/platform/web
releases. The bridge job number was misread as an HTTP status, the deployed
database did not contain the Landing migration, and the live bridge exposed the
wrong mode set. Device login also lacked a pseudo-terminal and outbound network;
ANSI styling hid its one-time code, login status did not prove model execution,
and the regenerated root credential was unreadable by the non-root worker.
Finally, the current Codex JSON stream did not expose nested image-tool arguments,
so the old enhancement proof rejected a valid observable flow.

**Durable fix:** deployed one versioned compatible set for Commander, Validation,
Owner Gateway, platform API/worker/auth, both schema migrations, and Firebase
Hosting. The private auth service now uses a pseudo-terminal, outbound edge
access, ANSI-safe parsing, bounded real-request retries, and a root-owned
group-readable credential handoff to the non-root worker. Enhancement acceptance
uses exact private reference validation plus a distinct output digest. The
serial publisher stops before reset whenever provider canaries fail. The
owner-confirmed irreversible reset ran only after every canary passed.

**Verification:** all six services are healthy on the same release; exact bridge
capabilities, ChatGPT/Codex working authorization, secure worker credential
readability, all structured/media/Pexels canaries, public Hosting markers, App
Check/CORS/auth boundaries, schema idempotency, local suites, Commander demo, and
skill checks pass. The reset left every Brief, Studio, Landing, and graph business
table empty while the independent platform database snapshot remained unchanged.
Both emergency stops are false, the resource audit passed, and its 24-hour
follow-up timer is active.

The retired Social posts/Result incident history is available only in Git
history. Record future Product Brief, Studio, Owner Gateway, Firebase, Commander,
or Telegram emergency incidents here with symptom, cause, durable fix,
verification, and the narrowest reusable skill update. Never record secrets or
ephemeral release hashes.
