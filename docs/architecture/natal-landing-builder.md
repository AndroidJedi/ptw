# Natal Landing v2

Natal remains the fixed identity and three-layout system. Landing accepts only
an explicit active approved Positioning project/revision plus request UUID and
public HTTPS privacy URL. One strict `natal_landing_revision` call populates
private `product`, `community`, and `waitlist` snapshots.

`LandingPageContent` v2 has eight blocks: hero, problem, features, steps, proof,
FAQ, final CTA, and lead form. Edits receive whole-page context but return only
one selected block. Proof, Positioning facts/IDs, privacy URL, form definitions,
publication target, and graph IDs remain protected.

The form catalog is code-owned:

| Form | Fields | Submit label |
| --- | --- | --- |
| `waitlist` | email | Join waitlist / Приєднатися до списку |
| `contact_request` | name, email, optional note | Send request / Надіслати запит |
| `community_interest` | name, email, optional Telegram | I’m interested / Хочу приєднатися |

The agent chooses the form ID and writes only heading/body. Validation, consent
and privacy link, success text, notification, and fields are rendered from code.
Authenticated previews are self-contained, no-store, sandboxed, and inert.

Publication consumes the exact selected current snapshot/digest without an
agent call and activates the form only in that public build. Private manifest
JSON never enters the Firebase release. Published submissions enforce exact
field allowlists, honeypot, bounds, email validation, HMAC IP rate limiting,
and HMAC dedupe without raw IP retention. Commit precedes Telegram; send failure
never changes visitor acceptance.
