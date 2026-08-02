# PTW — Prove Them Wrong

Bold, offline Flutter prototype built around one viral loop:

**Create a project → share its link → receive an anonymous message and
Believe/Doubt position → read it in the private creator inbox.**

Every project is represented by a mandatory image and creator-selected primary
color. The shared page is intentionally short: visitors see the goal, choose a
side, write one anonymous message, and send. The creator's current project is a
dedicated full-bleed page with its latest proof, recent private responses, and
a derived social activity feed.

## Local prototype data

Bundled JSON and images seed the first launch. A versioned JSON snapshot is then
stored under `ptw.prototype.snapshot.v2` with `SharedPreferencesAsync`. Projects,
responses, read state, and evidence survive app restarts. This is intentionally
prototype-only persistence, not a production database.

Creators can choose a bundled project image or import one from the device photo
library. Imported files are copied into application documents before their
relative paths are stored.

Public routes:

- `/:handle` — the owner's current project
- `/p/:projectId` — a specific project response page
- `/p/:projectId/sent` — response confirmation

Creator routes:

- `/`, `/inbox`, `/feed`
- `/projects/new`
- `/projects/:projectId/share`
- `/projects/:projectId/proof/new`

Product design decisions are captured in [DESIGN_RULES.md](DESIGN_RULES.md).

## Run and verify

```sh
flutter pub get
flutter run
flutter analyze
flutter test
```
