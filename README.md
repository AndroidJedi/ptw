# PTW — Prove Them Wrong

Bold, offline Flutter prototype built around one share-first viral loop:

**Open a ready Story → edit its headline or photo → copy its link → share it →
receive anonymous Believe/Doubt responses.**

Every creator share entry opens one automatically selected Story from the
synchronized schema-v3 catalog. A clean install is immediately usable with
sample content and the startup image. The runtime editor exposes only headline,
template, headline, photo/crop, **Generate Another**, and **Continue**. The
first Story uses the catalog's grainy `static_note_1` stone treatment. The
Template control changes authored layouts in place, while Generate Another rotates
deterministically through the internal three-candidate set without opening a
gallery. The exact visible composition is exported as a 1080×1920 PNG. Copy
activates a draft without closing the editor, while Share Story walks through
the Instagram link guide before opening the native operating-system share
sheet.

Later challenge creation asks for one required goal. Category and journey are
inferred metadata; doubt, metric, deadline, and candidate selection are not
part of the primary flow. The shared page is intentionally short: visitors see
the goal, choose a side, write one anonymous message, and send. The creator's
current project is a dedicated full-bleed page with its latest proof, recent
private responses, and a derived social activity feed.

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
The selective documentation map and Commander architecture are in
[docs/README.md](docs/README.md); agents should start there instead of loading
the entire documentation tree.

## Build-time template generation

PTW templates can be authored by Codex through the repository-local STDIO MCP
server. The canonical catalog lives at
`tool/ptw_template_mcp/catalog/share_theme.json`; a pre-run MCP client validates
and synchronizes it into the bundled Flutter theme. Codex is the creative
author, while the MCP server enforces schema-v3, versioning, safe-zone, existing
asset/layer, and readiness constraints. No AI, MCP, HTTP, or network dependency
is present in the running app.

After opening a fresh Codex session so `.codex/config.toml` is discovered,
author through the `author_ptw_template` prompt or the context → validate →
upsert tool sequence. Synchronize or check the deterministic output with:

```sh
dart run tool/ptw_template_mcp/sync.dart
dart run tool/ptw_template_mcp/sync.dart --check
```

The architecture, complete authoring instructions, tool/resource contract, CI
workflow, and troubleshooting guide are in
[docs/PTW_TEMPLATE_MCP.md](docs/PTW_TEMPLATE_MCP.md).

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
dart run tool/ptw_template_mcp/sync.dart --check
flutter run
flutter analyze
flutter test
flutter build web -t lib/share_theme_builder_main.dart
```
