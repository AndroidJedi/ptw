import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled PTW theme validates and round-trips', () async {
    final theme = await ShareThemeBundle.loadAsset();
    expect(theme.id, 'ptw_story_v1');
    expect(theme.looks, hasLength(18));
    expect(theme.canvas.outputWidth, 1080);
    expect(theme.canvas.outputHeight, 1920);
    expect(theme.maximumDecorationCount, 6);
    expect(theme.toolbar.map((item) => item.id), [
      'templates',
      'text',
      'looks',
      'photo',
      'effects',
      'decor',
    ]);
    expect(
      theme.looks.where((item) => item.editorVisible).map((item) => item.label),
      [
        'Soft Focus 1',
        'Soft Focus 2',
        'Soft Focus 3',
        'Pixel Pop 1',
        'Pixel Pop 2',
        'Pixel Pop 3',
        'Static Note 1',
        'Static Note 2',
        'Static Note 3',
        'Holo Crush 1',
        'Holo Crush 2',
        'Holo Crush 3',
        'Peach Collage 1',
        'Peach Collage 2',
        'Peach Collage 3',
      ],
    );
    for (final family in const [
      'soft_focus',
      'pixel_pop',
      'static_note',
      'holo_crush',
      'peach_collage',
      'legacy_victory',
    ]) {
      final variants =
          theme.looks
              .where((item) => item.id.startsWith('${family}_'))
              .toList();
      expect(variants.map((item) => item.id), [
        '${family}_1',
        '${family}_2',
        '${family}_3',
      ]);
      expect(
        variants
            .map((item) => jsonEncode(item.backgroundTreatment.toJson()))
            .toSet(),
        hasLength(3),
        reason: '$family variants must use three different photo treatments',
      );
      expect(
        variants.map((item) => jsonEncode(item.layerOverrides)).toSet(),
        hasLength(3),
        reason: '$family variants must use three different type treatments',
      );
      expect(
        variants
            .map(
              (item) => jsonEncode(
                item.defaultStickers
                    .map((sticker) => sticker.toJson())
                    .toList(),
              ),
            )
            .toSet(),
        hasLength(3),
        reason: '$family variants must use three different decorations',
      );
    }
    expect(
      theme.looks
          .where((item) => item.id.startsWith('legacy_victory_'))
          .every((item) => !item.editorVisible),
      isTrue,
    );
    expect(
      theme.assets
          .where((item) => item.kind == 'font')
          .map((item) => item.fontFamily),
      containsAll(['PtwPressStart2P', 'PtwRubikDirt']),
    );
    final decoded = ShareThemeConfig.fromJson(
      jsonDecode(ShareThemeBundle.toJsonString(theme)) as Map<String, dynamic>,
    );
    expect(decoded.toJson(), theme.toJson());
  });

  test('missing photo-first fields retain defaults', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    source.remove('maximumDecorationCount');
    for (final look in (source['looks'] as List<dynamic>).cast<Map>()) {
      look.remove('backgroundTreatment');
      look.remove('editorVisible');
    }

    final legacy = ShareThemeConfig.fromJson(source);

    expect(legacy.schemaVersion, ShareThemeConfig.currentSchemaVersion);
    expect(legacy.maximumDecorationCount, legacy.maximumStickerCount);
    expect(legacy.looks.every((item) => item.editorVisible), isTrue);
    expect(
      legacy.looks.every(
        (item) =>
            item.backgroundTreatment.texture == ShareBackgroundTexture.none,
      ),
      isTrue,
    );
  });

  test('schema v1 themes migrate to an open legacy template', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    source['schemaVersion'] = 1;
    source.remove('templates');
    source.remove('defaultTemplateId');
    source.remove('designSystemVersion');
    for (final layer in (source['layers'] as List<dynamic>).cast<Map>()) {
      layer.remove('semanticRole');
      layer.remove('emphasis');
      layer.remove('runtimePermissions');
    }

    final migrated = ShareThemeConfig.fromJson(source);

    expect(migrated.schemaVersion, ShareThemeConfig.currentSchemaVersion);
    expect(migrated.defaultTemplateId, 'legacy_default');
    expect(migrated.templates.single.family, ShareTemplateFamily.unassigned);
    expect(
      migrated.layers.every((layer) => layer.runtimePermissions.canMove),
      isTrue,
    );
  });

  test('look background treatment ranges are validated', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    final look =
        (source['looks'] as List<dynamic>).first as Map<String, dynamic>;
    (look['backgroundTreatment'] as Map<String, dynamic>)['imageOpacity'] = 0.1;

    expect(() => ShareThemeConfig.fromJson(source), throwsFormatException);
  });

  test('canvas corner radius round-trips and validates its bounds', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    final canvas = Map<String, dynamic>.from(source['canvas'] as Map)
      ..['cornerRadius'] = 24;
    final rounded = ShareThemeConfig.fromJson({...source, 'canvas': canvas});
    expect(rounded.canvas.cornerRadius, 24);
    expect(
      (rounded.toJson()['canvas'] as Map<String, dynamic>)['cornerRadius'],
      24,
    );

    canvas['cornerRadius'] = 181;
    expect(
      () => ShareThemeConfig.fromJson({...source, 'canvas': canvas}),
      throwsA(
        isA<FormatException>().having(
          (error) => error.message,
          'message',
          contains('cornerRadius'),
        ),
      ),
    );
  });

  test('unknown versions and duplicate IDs are rejected', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    expect(
      () => ShareThemeConfig.fromJson({...source, 'schemaVersion': 99}),
      throwsFormatException,
    );
    final duplicate = jsonDecode(jsonEncode(source)) as Map<String, dynamic>;
    final layers = duplicate['layers'] as List<dynamic>;
    layers.add(Map<String, dynamic>.from(layers.first as Map));
    expect(() => ShareThemeConfig.fromJson(duplicate), throwsFormatException);
  });

  test(
    'bounds, gradients, bindings, assets, and access errors are actionable',
    () async {
      final raw = await rootBundle.loadString(ShareThemeBundle.defaultAsset);
      Map<String, dynamic> source() => jsonDecode(raw) as Map<String, dynamic>;

      final bounds = source();
      ((bounds['layers'] as List<dynamic>).first
          as Map<String, dynamic>)['transform'] = {
        'x': -1,
        'y': 0,
        'width': 360,
        'height': 640,
      };
      expect(
        () => ShareThemeConfig.fromJson(bounds),
        throwsA(
          isA<FormatException>().having(
            (error) => error.message,
            'message',
            contains('outside the canvas'),
          ),
        ),
      );

      final gradient = source();
      final backgrounds =
          (gradient['backgrounds'] as List<dynamic>)
              .cast<Map<String, dynamic>>();
      final hot = backgrounds.singleWhere(
        (item) => item['id'] == 'gradient_hot',
      );
      (hot['properties'] as Map<String, dynamic>)['stops'] = [0.8, 0.2];
      expect(
        () => ShareThemeConfig.fromJson(gradient),
        throwsA(
          isA<FormatException>().having(
            (error) => error.message,
            'message',
            contains('invalid stops'),
          ),
        ),
      );

      final binding = source();
      final layers =
          (binding['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
      layers.singleWhere((item) => item['id'] == 'headline')['binding'] = 'bad';
      expect(() => ShareThemeConfig.fromJson(binding), throwsFormatException);

      final asset = source();
      final assetLayers =
          (asset['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
      (assetLayers.singleWhere((item) => item['id'] == 'avatar')['style']
              as Map<String, dynamic>)['fallbackAssetId'] =
          'missing';
      expect(() => ShareThemeConfig.fromJson(asset), throwsFormatException);

      final access = source();
      final toolbar =
          (access['toolbar'] as List<dynamic>).cast<Map<String, dynamic>>();
      toolbar.first['access'] = {'mode': 'premiumVisible'};
      expect(() => ShareThemeConfig.fromJson(access), throwsFormatException);
    },
  );
}
