import 'dart:convert';

import '../../generated_share_editor/generated_share_editor.dart';

const _legacyLookIds = <String, String>{
  'project_focus': 'soft_focus_1',
  'hot_dare': 'pixel_pop_1',
  'night_detective': 'static_note_1',
  'candy_hype': 'holo_crush_1',
  'yellow_chaos': 'peach_collage_1',
  'sky_victory': 'legacy_victory_1',
};

/// Upgrades the stock six-look builder draft to the numbered look catalog.
///
/// Existing edits to each original look become that family's `_1` variant.
/// The bundled `_2` and `_3` variants are inserted alongside it, while any
/// user-created looks and other theme edits remain intact.
ShareThemeConfig migrateThemeBuilderDraft({
  required ShareThemeConfig saved,
  required ShareThemeConfig bundled,
}) {
  final savedIds = saved.looks.map((look) => look.id).toSet();
  final bundledIds = bundled.looks.map((look) => look.id).toSet();
  if (!_legacyLookIds.keys.every(savedIds.contains) ||
      !_legacyLookIds.values.every(bundledIds.contains) ||
      _legacyLookIds.values.any(savedIds.contains)) {
    return saved;
  }

  final savedJson = _deepCopy(saved.toJson());
  final bundledJson = _deepCopy(bundled.toJson());
  final savedLooks = _objects(savedJson['looks']);
  final bundledLooks = _objects(bundledJson['looks']);
  final savedById = {for (final look in savedLooks) look['id'] as String: look};
  final legacyIdForNumbered = {
    for (final entry in _legacyLookIds.entries) entry.value: entry.key,
  };

  for (final collection in const ['assets', 'backgrounds', 'stickers']) {
    _addMissingById(savedJson, bundledJson, collection);
  }

  savedJson['looks'] = [
    for (final bundledLook in bundledLooks)
      if (legacyIdForNumbered[bundledLook['id']] case final legacyId?)
        {
          ...savedById[legacyId]!,
          'id': bundledLook['id'],
          'label': bundledLook['label'],
          'editorVisible': bundledLook['editorVisible'],
        }
      else
        bundledLook,
    for (final savedLook in savedLooks)
      if (!_legacyLookIds.containsKey(savedLook['id'])) savedLook,
  ];
  final oldDefault = savedJson['defaultLookId'] as String;
  savedJson['defaultLookId'] = _legacyLookIds[oldDefault] ?? oldDefault;

  try {
    return ShareThemeConfig.fromJson(savedJson);
  } on FormatException {
    // A heavily customized catalog may not support the bundled variants. Its
    // valid draft is safer than discarding it or preventing the builder load.
    return saved;
  }
}

Map<String, dynamic> _deepCopy(Map<String, dynamic> source) =>
    jsonDecode(jsonEncode(source)) as Map<String, dynamic>;

List<Map<String, dynamic>> _objects(Object? source) =>
    (source as List<dynamic>).cast<Map<String, dynamic>>();

void _addMissingById(
  Map<String, dynamic> target,
  Map<String, dynamic> source,
  String collection,
) {
  final targetItems = _objects(target[collection]);
  final existingIds = targetItems.map((item) => item['id'] as String).toSet();
  for (final item in _objects(source[collection])) {
    if (existingIds.add(item['id'] as String)) targetItems.add(item);
  }
  target[collection] = targetItems;
}
