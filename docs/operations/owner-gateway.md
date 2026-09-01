# Owner Gateway operations

Owner Console uses Firebase Auth, pinned verified owner identity, and App Check.
Owner Gateway is the only normal instruction channel and proxies bounded Project,
Product Brief, five-Creative review, approved export, and owner-only Studio APIs.
Domain data is never stored in Firebase or service-worker caches.

Social creation accepts only request ID, approved Brief ID, and optional
Instagram/TikTok platform. The Gateway maps platform to the fixed server task.
A successful generation displays five authenticated Creative cards and exposes
web-only Approve, Regenerate all, and Tune-with-comment actions. The owner never
enters an internal UUID; selection resolves it in the UI/API.

Run state is queued, generating, awaiting_review, approved, superseded, failed,
plus loopback-only terminated. Review assets and exports are authenticated,
private/no-store, digest checked, and proxied byte-for-byte. Only an approved
Creative export is available.

Notification state is part of the review projection. A definite or ambiguous
failure never hides the five cards. Manual notification retry is authenticated.
Telegram itself accepts no review action and remains `/help`, `/status`, `/stop`
plus outbound notifications.

Owner learning is append-only. The UI may display action UUIDs, Creative UUIDs,
child lineage, exact tune comments, and active Project rules. It does not expose
subjective evaluation, comparisons, automatic selection, prompt contents,
credentials, raw media bytes, task fields, templates, sliders, or manual brand
setup in the normal journey.

The loopback app additionally supports approved local assets/Pexels through the
Studio flow, saved Universal Studio state, local terminate, full Creative ZIP
export, and file authority below `.local/owner-experiments`. Social posts does
not duplicate asset sourcing, Project evidence, or run/snapshot history. Bind
the loopback app only to `127.0.0.1`.

The PWA service worker caches only public shell assets. API, authenticated image,
review, export, feedback, rule, and notification responses are never cached.

Production release remains confirmation gated and reset-only for the new clean
baseline. The unrelated platform repository and database are never reset or
merged. No rollout is authorized by local implementation work.
