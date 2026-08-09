# PTW Post Generator — Implemented State Handoff

This document describes the post generator exactly as it exists in the current working tree after the template-system enhancement. It is intended as implementation context for another agent. It does not claim that the code implements every item from the broader PTW framework or roadmap.

No generative AI is involved in the current implementation. “Generation” means deterministic content selection, template/look composition, Flutter rendering, persistence, and PNG export.

## 1. Live architecture

The live creator flow is a schema-driven Instagram Story generator:

1. `lib/features/story/share_story_preview_screen.dart` resolves a project, share event, moment, and saved draft.
2. `lib/features/story/ptw_generated_story_adapter.dart` converts PTW data into `ShareEditorContent` and `ShareEditorValue`.
3. `lib/generated_share_editor/config/share_theme.json` defines reusable layers, structural templates, visual looks, safe zones, permissions, assets, controls, and metadata.
4. `ShareEditorController` composes base layer → template override → look override → saved user transform/style override.
5. `GeneratedShareEditor` exposes only the controls permitted by the active runtime template.
6. `GeneratedShareRenderer` is shared by on-screen preview and export.
7. `SharePngExporter` renders the exact current value to a 1080×1920 PNG.
8. The app copies the PTW link, shows the four-step Instagram Link-sticker guide, and opens the native share sheet.

The live controller is explicitly created with `ShareEditorMode.runtime`. The internal theme builder uses authoring behavior.

## 2. Schema and composition model

The theme schema is version 2. Schema-v1 themes are migrated in memory to v2 with an open `legacy_default` template, unassigned semantic roles, and permissive legacy layer/runtime permissions.

### Structure and appearance are separate

- `ShareTemplateConfig` owns structure and product behavior: family, variant, narrative intent, journey states, semantic requirements, primary anchor, media count, proof/comparison capability, safe zones, runtime permissions, versions, status, and structural layer overrides.
- `ShareLookConfig` owns visual treatment: background choice/treatment, layer style overrides, and preset stickers.
- `ShareLayerConfig` owns the reusable component definition, semantic role, emphasis, base transform/style, controls, access policy, and layer-level runtime permissions.
- `ShareEditorValue` owns creator state. It now persists `templateId` in addition to `lookId`, content overrides, transforms, style properties, background treatment, stickers, and uploaded overlays.

Effective rendering order is:

1. Base layer.
2. Active template override.
3. Active look override.
4. Saved creator transform and exposed property overrides.

Changing a template clears saved transforms and property overrides so an old structure cannot leak into the new one. It preserves creator content values and the active look.

### Semantic vocabulary

Implemented template families include `heroPhoto`, `progress`, `comparison`, plus reserved roadmap families such as proof, conflict, milestone, documentary, reflection, recovery, and result.

Implemented journey states include beginning, grind, small win, setback, failure, recovery, milestone, reflection, and result.

Layer semantic roles include hero/previous/current media, headline, challenge, criticism, proof, metric, progress, time, goal, avatar, brand, and semantic decoration. Every layer also has primary, secondary, or tertiary emphasis.

## 3. Experimental templates

The bundled theme contains three experimental templates.

### Hero Photo (`hero_photo`)

- Family: Hero Photo.
- Default template.
- One media source.
- Visible structure: background hero image, avatar, headline, challenge/dare, PTW footer, and look-owned preset artwork.
- Primary anchor: headline.
- Intended for beginning, grind, small-win, setback, recovery, milestone, reflection, and result moments.

### Progress (`progress`)

- Family: Progress.
- One media source.
- Visible structure: background image, upper headline, large progress value, proof metric, challenge/dare, and PTW footer.
- Primary anchor: progress.
- Supports proof and journey states grind, small win, recovery, milestone, and result.

### Comparison (`comparison`)

- Family: Comparison.
- Two distinct semantic media slots: `previous_media` and `current_media`.
- Includes previous/current time labels, lower headline, optional challenge/dare, and PTW footer.
- Primary anchor: current media.
- Supports comparison and proof for small-win, recovery, milestone, reflection, and result moments.

The current PTW project domain has only one project image. The live adapter therefore initializes both comparison slots from the current project background as a safe fallback. The two slots are independent editor values and can be replaced separately at runtime.

## 4. Generated content

For a new Story:

- Headline is the trimmed project goal.
- Dare is deterministic from the share event:
  - Milestone: `Still doubting?`
  - New skeptic, first comment, or top-comment change: `They said I won’t. Agree?`
  - New supporter or weekly progress: `They believe. Do you?`
  - Completed goal: `I did it. What now?`
  - Otherwise: `Think I won’t?`
- Caption is headline + newline + dare.
- Public link is `https://ptw.to/p/{projectId}`.
- Previous/current comparison media initially use the project image.
- Previous/current time labels are `BEFORE` and `NOW`.
- Progress is `100%` for completed projects and `IN PROGRESS` otherwise.
- Metric text is `GOAL COMPLETED` for completed projects and `STILL SHOWING UP` otherwise.
- The event name is available as a proof label.

Owner name, handle, event, moment ID, deadline, and custom values remain available to bindings even when the selected template does not display them.

## 5. Creator-facing runtime permissions

The mobile flow no longer exposes the full authoring surface. Its toolbar is derived from template permissions and currently exposes:

- Layout: choose Hero Photo, Progress, or Comparison.
- Text: edit the visible permitted headline/challenge fields; Progress additionally exposes its progress and metric values.
- Photo: replace/crop the main image and replace any visible permitted image slots, including previous/current comparison media.

The bundled templates allow alternate-template selection, media replacement/crop, headline editing, optional challenge editing, and—in Progress—proof-value editing.

The live runtime does not expose:

- Look selection.
- Font, color, text-effect, or arbitrary style changes.
- Layer dragging, resizing, or rotation.
- Photo filters or texture adjustments.
- Built-in sticker selection or uploaded decorations.
- Generic background catalog selection.

Look-owned preset artwork may still render as fixed template artwork, but runtime users cannot add, transform, or delete it.

Permissions are enforced by the controller as well as hidden in the UI. Calling a disallowed mutation returns `false`; the restriction is not only presentational.

## 6. Authoring/runtime separation

`ShareEditorMode.authoring` keeps the reusable editor’s full capabilities for internal authoring and compatibility. `ShareEditorMode.runtime` combines template-level and layer-level permission checks.

Template-level permissions cover:

- Replace/crop media.
- Edit headline.
- Edit proof value.
- Choose another template.
- Hide an optional note.
- Edit decorations.

Layer-level permissions cover:

- Edit content.
- Replace/crop media.
- Move, resize, or rotate.
- Style.
- Hide.

Legacy schema-v1 migration deliberately grants all permissions so importing an old theme does not silently remove behavior.

## 7. Safe zones and export parity

Each experimental template declares five guide types:

- Instagram top danger.
- Instagram bottom danger.
- Recommended Link-sticker area.
- Protected subject/evidence area.
- Brand-safe footer area.

`GeneratedShareRenderer(showAuthoringGuides: true)` draws labeled translucent overlays. The internal builder exposes a safe-zone toggle. Guides use `IgnorePointer` and are opt-in; the PNG exporter never enables them.

Preview and PNG export still use the same renderer and serialized value. Existing 1080×1920 export, photo-treatment, font, decoration, and golden tests remain green.

## 8. Persistence and migration

`PtwStoryComposition` persists the PTW-facing Story data and the exact nested `ShareEditorValue`.

The nested editor value includes:

- Template ID and look ID.
- Layer values, including independent comparison media.
- Creator transforms/style properties when allowed by the source mode.
- Background image, crop, zoom, and treatment.
- Built-in stickers and uploaded overlays for compatibility.

The adapter restores saved values when the theme ID matches and the saved theme schema is not newer than the current schema. A schema-v1 saved value has no `templateId`; controller validation assigns the current default template. Invalid/newer/incompatible values fall back to conversion from the top-level legacy Story fields.

Onboarding edits autosave approximately 300 ms after changes and are persisted immediately before continue/close. Existing-project compositions are stored with share history. Imported media is copied to the application documents `ptw_media/` directory and persisted by relative path.

## 9. Internal theme builder

Launch with:

```sh
flutter run -d chrome -t lib/share_theme_builder_main.dart
```

The builder now has two modes:

- Explore edits reusable base layers, looks, assets, controls, toolbar, access, and visual styling.
- Production edits the selected template’s structural transforms/visibility and focuses the inspector on template metadata, semantic roles, and permissions.

Implemented builder capabilities include:

- Template selector.
- Template family, primary journey state, variant, narrative intent, primary anchor, media count, proof/comparison flags, required/optional semantic roles, and runtime permissions.
- Layer semantic role, emphasis, and layer-level runtime permissions.
- Safe-zone preview toggle.
- Deterministic PTW validation panel with readiness score, blocking errors, warnings, and notes.
- ZIP generation blocked when any bundled template has a validation error.
- Existing undo/redo, grid/snap, JSON import/export, asset/font import, autosave, visual look editing, and deterministic package export.

Current validator checks family/journey metadata, anchor-role consistency, visible required roles, PTW brand/headline presence, comparison/proof structure, five safe-zone types, PTW font family use, excessive type scale, and runtime permission consistency.

Hero Photo scores 100 apart from its experimental note. Progress and Comparison are export-ready but intentionally retain a non-blocking hierarchy warning because each currently contains two layers marked with primary emphasis. This is visible work for a later design pass, not a hidden failure.

## 10. Exported package contract

The generated ZIP remains self-contained and deterministic. It contains runtime Dart sources, the v2 runtime theme, portable source theme, content-hashed assets, README, and pubspec snippet.

Its README now instructs hosts to create `ShareEditorController(mode: ShareEditorMode.runtime)`, persist `ShareEditorValue.templateId`, treat templates as structure and looks as appearance, and keep safe-zone overlays authoring-only.

## 11. Intentional boundaries and remaining work

This enhancement implements only the first requested slice. It does not add:

- Automatic journey-state selection from all domain events.
- A real historical “before” photo source in the PTW project model.
- Face/person detection or automatic subject-safe cropping.
- Automatic placement of Instagram’s Link sticker.
- Animation metadata or animated export.
- Runtime experimentation analytics or template ranking.
- A full design-system token registry beyond the current PTW font checks and theme values.
- Automated measurement of creation time or share conversion.
- Direct Instagram publishing.

The repository also retains older `lib/features/share/` and `lib/features/social_post_studio/` generators for compatibility/tests. They are not the live generated-editor route.

## 12. Primary editing surfaces

- Schema, experimental templates, semantic roles, safe zones, looks, and assets: `lib/generated_share_editor/config/share_theme.json`
- Schema classes and v1→v2 migration: `lib/generated_share_editor/src/share_theme.dart`
- Serializable content/value model: `lib/generated_share_editor/src/share_value.dart`
- Structure/look composition and runtime enforcement: `lib/generated_share_editor/src/share_controller.dart`
- Runtime panels and toolbar filtering: `lib/generated_share_editor/src/share_editor.dart`
- Shared rendering and authoring guides: `lib/generated_share_editor/src/share_renderer.dart`
- PTW content/value adapter and legacy saved-value restoration: `lib/features/story/ptw_generated_story_adapter.dart`
- Live runtime controller setup, draft/export/share flow: `lib/features/story/share_story_preview_screen.dart`
- Builder state and Explore/Production structural editing: `lib/features/share_theme_builder/theme_builder_controller.dart`
- Builder UI: `lib/features/share_theme_builder/share_theme_builder_app.dart`
- Deterministic readiness checks: `lib/features/share_theme_builder/ptw_template_validator.dart`
- Generated ZIP assembly and README contract: `lib/features/share_theme_builder/theme_package_exporter.dart`

## 13. Verification

Verified on 2026-08-08 in the current uncommitted `onboarding` working tree:

- `flutter analyze`: no issues.
- Full `flutter test`: all 113 tests passed.
- Schema-v1 theme migration and legacy value migration covered.
- Template/look composition and runtime permission enforcement covered.
- All three bundled templates pass blocking PTW validation.
- Safe-zone overlays are opt-in and absent by default.
- Comparison template selection persists through the live share flow.
- Existing renderer/export goldens and exact 1080×1920 PNG tests pass.

The working tree already contained unrelated uncommitted media/theme/editor work before this enhancement. Those changes remain preserved.
