# PTW incident log

Updated: 2026-09-06

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
