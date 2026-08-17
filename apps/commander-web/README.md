# Commander Web

Mobile-first React/Vite PWA for the PTW owner. Firebase provides Google Auth and
App Check; every API request still receives independent gateway verification.

```sh
npm ci
npm run check
npm run test:e2e
```

Configuration:

- `VITE_COMMANDER_API_URL=https://commander.proove-them-wrong.com`
- `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY=<public site key>`

The service worker caches document/script/style/font shell resources only. It
does not handle API routes, images, WebSockets, or terminal traffic.
