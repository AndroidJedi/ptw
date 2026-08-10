# PTW build-time MCP template pipeline

PTW uses a local Model Context Protocol (MCP) boundary to turn a creative
template idea into validated schema-v3 configuration before the Flutter app
starts. The application itself remains fully offline: it never starts an MCP
server, contacts an AI service, or downloads generated assets.

## Theoretical overview

MCP separates reasoning from execution. Codex supplies the creative reasoning,
while the PTW MCP server supplies a small, explicit capability surface backed
by the repository's real schema and validator. This makes the model an author
of declarative data rather than an author of executable runtime code.

The pipeline has four boundaries:

1. **Authoring catalog** —
   `tool/ptw_template_mcp/catalog/share_theme.json` is the canonical state that
   Codex reads and updates.
2. **MCP policy server** — `server.dart` exposes context, validation, upsert,
   export, resources, and a prompt over STDIO. It restricts proposals to known
   schema fields, layers, assets, looks, safe typography, safe zones, and PTW
   readiness rules.
3. **Build-time synchronization client** — `sync.dart` launches the server as a
   subprocess, verifies tool discovery, exports the catalog, validates it again
   locally, and atomically updates the Flutter JSON only when bytes changed.
4. **Offline Flutter runtime** — PTW bundles
   `lib/generated_share_editor/config/share_theme.json` and uses its existing
   deterministic candidate generator and renderer. There is no MCP or network
   dependency after the app starts.

The catalog revision is a deterministic FNV-1a hash of normalized catalog JSON.
Writers must send the revision they read. This optimistic-concurrency check
prevents a stale authoring session from overwriting newer work. New template IDs
start at `templateVersion: 1`; replacements use the current version plus one.
An identical retry is idempotent. Validation failures and stale revisions do
not modify the catalog, while warnings are returned but remain non-blocking.

Atomic same-directory temporary-file renames protect both catalog updates and
runtime synchronization. Consequently, a failed operation leaves readers with
the complete old file rather than a partially written new file.

## Ready-Story runtime model

The build-time catalog and the runtime entry flow solve different problems:
the catalog defines what PTW is allowed to render, while the app supplies local
project content and chooses one eligible composition. Keeping that boundary
explicit means a generated template cannot add executable code, networking, or
new assets, and the app never needs an MCP connection to display a Story.

On a clean local snapshot, `PtwAppState` creates a first-project draft from the
synchronized theme's `sampleContent`, the bundled startup image, an inferred
category, and the beginning journey state. It does this only when the account
is unactivated and there is no meaningful draft. Existing non-empty drafts and
activated projects are preserved.

Every share entry then follows the same deterministic sequence:

1. Infer category, journey, event, and available evidence as private metadata.
2. Rank all eligible production templates from the bundled catalog.
3. Generate the internal three-candidate set and select its highest-ranked
   member with `generatePreferred`.
4. Apply the grainy `static_note_1` treatment on the initial composition and
   open it directly in the editor. There is no journey prompt or candidate
   gallery.
5. On **Generate Another**, increment the regeneration index, build the next
   stable candidate set, rotate to the next family/look, and remain in the
   editor. The user's headline and photo/crop edits are retained.

The runtime surface intentionally exposes only Template, headline editing,
photo replace and crop, Generate Another, and Continue. Template switches among
the catalog's authored layouts without leaving the editor. Looks, FX, Decor,
category, metric, and journey controls remain unavailable. During first-project
onboarding, headline edits also update `draft.goal`, so project activation uses
the words visible in the Story. Photo edits remain composition-only and never
silently replace the project's saved image.

To exercise the complete local path:

```sh
dart run tool/ptw_template_mcp/sync.dart --check
flutter test test/flows/clean_install_guard_flow_test.dart
flutter test test/flows/draft_persistence_flow_test.dart
tool/run_android.sh
```

## One-time setup

From the repository root:

```sh
flutter pub get
```

The project-scoped Codex MCP registration is in `.codex/config.toml`. Trust the
project when Codex asks, then start a **fresh Codex session** from this project;
an already-running session does not discover a newly added MCP server. The
configuration starts:

```sh
dart run tool/ptw_template_mcp/server.dart --stdio
```

Read-only tools may run normally. `upsert_template` is a write-class tool and
the project configuration requests approval for writes.

## Author a template with Codex

Ask Codex to use the `author_ptw_template` MCP prompt or follow this sequence:

1. Call `get_template_context`, optionally with `family` or `journeyState`.
2. Create one complete production `ShareTemplateConfig`. Use only returned
   IDs and enum values. Templates may only override `visible`, `transform`,
   `emphasis`, and `style.fontSize`, `style.minFontSize`, or `style.maxLines`.
3. Call `validate_template` and resolve every error. Warnings can be accepted.
4. Call `upsert_template` with the latest `catalogRevision` after approving the
   write. If the revision is stale, get context again and repeat validation.
5. Synchronize the generated runtime file:

   ```sh
   dart run tool/ptw_template_mcp/sync.dart
   ```

The server never accepts Dart code, new assets, external URLs, or new layer,
background, sticker, or look definitions. Generated "code" in this workflow
means schema-v3 JSON consumed by the already-compiled renderer.

## MCP contract

The server exposes four JSON-returning tools:

- `get_template_context({family?, journeyState?})` returns protocol, schema,
  design-system and catalog versions, enums, allowed IDs, constraints, layers,
  and relevant examples.
- `validate_template({template})` merges a proposal in memory and returns
  `valid`, `normalizedTemplate`, `score`, and issues without writing.
- `upsert_template({template, expectedCatalogRevision})` atomically adds or
  replaces a production template after full validation and revision checks.
- `export_runtime_theme({})` returns the complete normalized catalog and its
  revision for the synchronization client.

It also exposes:

- `ptw://template-generator/contract`
- `ptw://template-generator/catalog`
- `author_ptw_template`

Protocol messages use stdout. Server diagnostics use stderr so they cannot
corrupt the STDIO JSON-RPC stream.

## Run, synchronize, and verify

Normal synchronization is idempotent:

```sh
dart run tool/ptw_template_mcp/sync.dart
```

CI can detect a stale generated Flutter asset without modifying it:

```sh
dart run tool/ptw_template_mcp/sync.dart --check
```

The Android helper now performs dependency resolution and template sync before
launching Flutter:

```sh
tool/run_android.sh
```

Emulator-only behavior is unchanged and skips app preparation/launch:

```sh
tool/run_android.sh --emulator-only
```

Recommended verification:

```sh
dart run tool/ptw_template_mcp/sync.dart --check
flutter analyze
flutter test
```

## Repository layout

```text
.codex/config.toml                         Codex project MCP registration
tool/ptw_template_mcp/catalog/             canonical authoring catalog
tool/ptw_template_mcp/server.dart          local STDIO MCP server
tool/ptw_template_mcp/sync.dart            pre-run MCP synchronization client
lib/template_generator/                    pure-Dart policy/catalog service
lib/generated_share_editor/config/         deterministic Flutter output
```

Theme parsing is intentionally usable from plain Dart. Flutter `AssetBundle`
loading remains available through `ShareThemeBundle.loadAsset`; command-line
code reads the file and calls `ShareThemeBundle.fromJsonString`.

## Troubleshooting

- **Tools are not visible in Codex:** close the session, reopen the trusted PTW
  project, and start a fresh session so `.codex/config.toml` is loaded.
- **Stale catalog revision:** another write won the race. Fetch context again,
  revalidate the proposal, and upsert using the new revision.
- **`--check` reports a stale runtime theme:** run sync without `--check` and
  commit both the canonical catalog and generated runtime JSON when applicable.
- **Validation fails:** inspect returned `issues`. Errors block writes; warnings
  describe quality concerns and do not block installation.
- **STDIO parsing fails:** do not print diagnostics to stdout in the server.
  Logging belongs on stderr because stdout is reserved for MCP protocol frames.
