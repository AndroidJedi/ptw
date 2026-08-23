# PTW Owner Console

Mobile-first React/Vite PWA for the four PTW v2 workspaces: Marketing
Positioning, Landing, Ads, and Admin. Firebase supplies Google Auth and App
Check; Owner Gateway independently verifies both on every protected request.

```sh
npm ci
npm run check
npm run test:e2e
```

Production defaults to
`VITE_COMMANDER_API_URL=https://commander.proove-them-wrong.com`. The build
verifier checks the API origin, App Check header, public reCAPTCHA Enterprise
site key, Safari-safe Auth persistence, and service-worker markers.

Positioning displays source-explicit immutable revisions and approval. Landing
populates three fixed Natal templates from the active approved revision,
supports eight isolated block edits, publishes the exact selected snapshot, and
shows lead notification history. Ads is read-only and explicitly
unimplemented. Admin contains Jobs and Docs/System/Terminal.

The service worker caches only document/script/style/font shell resources. It
does not intercept APIs, previews, images, WebSockets, lead submission, or Auth
helper traffic.
