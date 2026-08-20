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
