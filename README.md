# PTW — Prove Them Wrong

Bold, offline Flutter prototype built around one share-first viral loop:

**Write a challenge → construct one playful Story → copy its link → share it →
receive anonymous Believe/Doubt responses.**

Every creator share entry opens the same Story-only constructor. Magic cycles
six deterministic PTW looks; the editor changes share-only text, a curated
background, and up to three draggable stickers. The exact visible composition
is exported as a 1080×1920 PNG. Copy activates a draft without closing the
constructor, while Share Story walks through an original four-step Instagram
link guide before opening the native operating-system share sheet.

Every project receives a publishable default image and color while deadline,
custom image, and doubt context remain optional. The shared page is intentionally
short: visitors see the goal, choose a
side, write one anonymous message, and send. The creator's current project is a
dedicated full-bleed page with its latest proof, recent private responses, and
a derived social activity feed.

## Local prototype data

Bundled JSON and images seed the first launch. A versioned JSON snapshot is then
stored under `ptw.prototype.snapshot.v5` with `SharedPreferencesAsync`. Projects,
responses, read state, evidence, draft Story edits, and share history survive
app restarts. v2–v4 snapshots migrate locally. This is intentionally
prototype-only persistence, not a production database.

Legacy share cards remain decodable in persisted history, but are no longer
loaded by the runtime. New share attempts persist the exact Story composition.

Creators can choose a bundled project image or import one from the device photo
library. Imported files are copied into application documents before their
relative paths are stored.

Public routes:

- `/:handle` — the owner's current project
- `/p/:projectId` — a specific project response page
- `/p/:projectId/sent` — response confirmation

Creator routes:

- `/` — share-first entry (draft onboarding or returning share layer)
- `/projects/:projectId`, `/inbox`, `/feed`
- `/projects/new`
- `/share/draft`
- `/projects/:projectId/share`
- `/projects/:projectId/proof/new`

Product design decisions are captured in [DESIGN_RULES.md](DESIGN_RULES.md).

## Share theme builder

The customer Story editor is schema-driven from
`lib/generated_share_editor/config/share_theme.json`. The canonical reusable
runtime lives in `lib/generated_share_editor/`; PTW supplies project content,
persistence, navigation, link copying, Instagram guidance, and native sharing.

Launch the internal desktop web builder with:

```sh
flutter run -d chrome -t lib/share_theme_builder_main.dart
```

The builder autosaves its working theme in browser storage. It can import or
export the portable versioned JSON (including embedded image/font bytes), and
**Generate ZIP** downloads one copyable `generated_share_editor/` directory.
That directory contains the Flutter-only runtime, extracted content-hashed
assets, runtime config, portable source JSON, integration README, and a
`pubspec.yaml` snippet. The normal PTW entry point remains `lib/main.dart`.

## Run and verify

```sh
flutter pub get
flutter run
flutter analyze
flutter test
flutter build web -t lib/share_theme_builder_main.dart
```
