# Commander Web

Mobile-first React/Vite PWA for the PTW owner. Firebase provides Google Auth and
App Check; every API request still receives independent gateway verification.

```sh
npm ci
npm run check
npm run test:e2e
```

Configuration:

- Production builds default to
  `VITE_COMMANDER_API_URL=https://commander.proove-them-wrong.com`; an explicit
  value can override it for a different deployment.
- The production reCAPTCHA Enterprise site key is public browser configuration
  and is committed with the Firebase app config. An explicit
  `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` can override it for another environment.

`npm run build` verifies that the production API origin, App Check header, and
site key survived compilation. Firebase Hosting also runs this build as a
predeploy check, so an incomplete or stale `dist` directory cannot be deployed.

The service worker caches document/script/style/font shell resources only. It
does not handle API routes, images, WebSockets, or terminal traffic.

The Ideas view contains only the Idea Laval Engine. No demo, fixture, seeded,
or C01–C10 ideas are displayed as owner data. Laval runs are created and
operated through the authenticated gateway; the browser
can inspect every stage, approve checkpoints, pause/resume, rerun a stage or
country, apply audited overrides, and download JSON/Markdown exports.
Completed runs also expose one primary `Завантажити PDF` action. The server
generates a concise Ukrainian report with visual summaries and bounded,
clickable HTTP(S) references; unfinished runs do not present it as a final
report.

The Branding view treats one completed live Idea as one continuous Brand
Project. It anchors the active approved kit/logo beside every draft and exposes
versioned run history, so a paused rebuild cannot hide the canonical identity.
The fixed evidence-backed pipeline still creates three directions, but primary
review is text-only and sequential—no annotations, ratings, palette specimens,
or owner-managed UUIDs.

An approved logo can be corrected directly without rerunning research. The
owner sees immutable Before/After assets, exact feedback, strategy, version, and
compliance status; approval creates a superseding kit and rejection preserves
the active one. Full rebuilding is an Advanced confirmed action. Asset and ZIP
responses are authenticated `private, no-store`. Exact lettermarks use bundled
fonts and code-owned rendering; the generated React kit remains code-owned and
includes licensed Cyrillic fonts.

The Landings view turns a completed live Idea evaluation into an editable Natal
landing brief. It recommends one of the product, community/event, or
waitlist/concept structures, keeps the source run and thesis IDs server-side,
and starts the dedicated deterministic `$natal-landing-builder` pipeline. Every
generated page keeps the Natal name, canonical logo, icons, and UI kit. A
successful build is published only to the server-pinned Natal Firebase Hosting
site; the tab polls its own durable history and exposes the exact public URL.
