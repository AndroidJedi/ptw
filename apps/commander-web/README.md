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
- `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY=<public site key>`

The service worker caches document/script/style/font shell resources only. It
does not handle API routes, images, WebSockets, or terminal traffic.

The Ideas view contains only the Idea Laval Engine. No demo, fixture, seeded,
or C01–C10 ideas are displayed as owner data. Laval runs are created and
operated through the authenticated gateway; the browser
can inspect every stage, approve checkpoints, pause/resume, rerun a stage or
country, apply audited overrides, and download JSON/Markdown exports.
