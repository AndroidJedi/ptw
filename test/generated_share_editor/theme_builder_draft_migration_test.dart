import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/theme_builder_draft_migration.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'legacy builder draft expands to six series without losing edits',
    () async {
      final bundled = await ShareThemeBundle.loadAsset();
      final source =
          jsonDecode(jsonEncode(bundled.toJson())) as Map<String, dynamic>;
      final looks =
          (source['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
      const oldIds = <String, String>{
        'soft_focus_1': 'project_focus',
        'pixel_pop_1': 'hot_dare',
        'static_note_1': 'night_detective',
        'holo_crush_1': 'candy_hype',
        'peach_collage_1': 'yellow_chaos',
        'legacy_victory_1': 'sky_victory',
      };
      final legacyLooks = <Map<String, dynamic>>[];
      for (final look in looks.where(
        (item) => oldIds.containsKey(item['id']),
      )) {
        final legacy =
            jsonDecode(jsonEncode(look)) as Map<String, dynamic>
              ..['id'] = oldIds[look['id']]!;
        legacyLooks.add(legacy);
      }
      final editedHeadline = Map<String, dynamic>.from(
        legacyLooks.first['layerOverrides'] as Map,
      );
      final headline = Map<String, dynamic>.from(
        editedHeadline['headline'] as Map,
      );
      final headlineStyle = Map<String, dynamic>.from(headline['style'] as Map)
        ..['color'] = '#FF00FF00';
      headline['style'] = headlineStyle;
      editedHeadline['headline'] = headline;
      legacyLooks.first['layerOverrides'] = editedHeadline;

      final custom =
          jsonDecode(jsonEncode(legacyLooks.first)) as Map<String, dynamic>
            ..['id'] = 'my_custom_look'
            ..['label'] = 'My custom look';
      source
        ..['looks'] = [...legacyLooks, custom]
        ..['defaultLookId'] = 'project_focus';
      final saved = ShareThemeConfig.fromJson(source);

      final migrated = migrateThemeBuilderDraft(saved: saved, bundled: bundled);

      expect(migrated.looks, hasLength(19));
      expect(migrated.looks.take(3).map((look) => look.id), [
        'soft_focus_1',
        'soft_focus_2',
        'soft_focus_3',
      ]);
      expect(migrated.defaultLookId, 'soft_focus_1');
      expect(
        migrated.look('soft_focus_1').layerOverrides['headline']!['style'],
        containsPair('color', '#FF00FF00'),
      );
      expect(migrated.looks.last.id, 'my_custom_look');
    },
  );

  test('numbered drafts are returned unchanged', () async {
    final bundled = await ShareThemeBundle.loadAsset();

    expect(
      migrateThemeBuilderDraft(saved: bundled, bundled: bundled),
      same(bundled),
    );
  });
}
