---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, Universal Studio, Commander, Validation, PostgreSQL, Pexels, and the existing Telegram emergency boundary.
---

# PTW Owner Console Incident

Trace a public symptom through browser → Firebase Hosting/Caddy → Owner Gateway
→ Validation → PostgreSQL or the independent structured bridge/Pexels API. A
healthy Gateway alone does not prove Product Brief or Studio readiness.

## Public boundary

- Verify hashed bundles, the current service-worker cache, Firebase Auth
  persistence, App Check, exact Owner CORS origins, and unauthenticated rejection.
- The normal app exposes Product Briefs and the owner-only Universal Studio.
  Social posts, content runs, Creative review, export, candidate generation,
  notifications, and their retired APIs must stay absent.
- Studio preview and immutable-version renders are authenticated, digest-checked,
  and private/no-store. The browser never receives provider or database secrets.
- Pexels imports must retain provider/license provenance and validate declared
  MIME against decoded bytes before persistence.
- Telegram inbound routing remains only `/help`, `/status`, and `/stop`; every
  other input returns the web-console link and cannot mutate application state.
  Never add another poller/webhook or print, rotate, or replace the token.

## Product Brief and Studio checks

- Product Brief remains raw idea → strict immutable hypothesis → correction →
  explicit owner approval. Corrections append HumanFeedback and WeightUpdate
  UUID entities with complete graph lineage.
- Provider modes are exactly `product_brief` and `product_brief_revision`; no
  media, candidate, evaluator, ranking, or selection mode is part of Validation.
- Universal Studio is a separate saved workspace. Keep its fixed semantic
  structure, strict bounded settings, deterministic primitive render, immutable
  approved versions, and Pexels-backed asset provenance.
- Restart recovery requeues only interrupted Product Brief generation. Studio
  state remains file-backed and independent of PostgreSQL Product Brief records.

## Release acceptance

Run the clean Product Brief schema verifier, built-image Validation and Owner
Gateway tests, Commander tests/demo, skill verification, web unit/build/
Playwright desktop and mobile, Studio visual audit, Python compilation, and
`git diff --check`. Before claiming Telegram works in production, verify
authorization, deployed help/routing, provider readiness, restart behavior, and
the user-facing failure path.
