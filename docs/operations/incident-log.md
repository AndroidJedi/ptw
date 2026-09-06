# PTW incident log

Updated: 2026-09-06

## 2026-09-06 — Studio route returned 404 in production

**Symptom:** authenticated Owner Console Studio requests reached
`/api/v1/studio` but received HTTP 404.

**Cause:** the Owner Gateway had been replaced independently while Validation,
Commander, and the platform bridge still used the retired Result release. The
proxy and downstream services therefore disagreed on the Studio route contract.

**Durable fix:** performed the confirmation-gated PTW reset and deployed one
versioned, compatible service set; published the matching Firebase Hosting
bundle and service worker. VPS operations now requires checking every running
public-service image before and after a cutover.

**Verification:** all containers reported healthy; the public gateway health
endpoint returned 200, unauthenticated Studio requests returned the expected
401 rather than 404, schema idempotency/skill checks/Commander tests and demo
passed, and the Commander schema reset postcondition was empty. The provider
generation canary remains blocked until the owner reauthorizes the revoked
ChatGPT device credential through Settings.

The retired Social posts/Result incident history is available only in Git
history. Record future Product Brief, Studio, Owner Gateway, Firebase, Commander,
or Telegram emergency incidents here with symptom, cause, durable fix,
verification, and the narrowest reusable skill update. Never record secrets or
ephemeral release hashes.
