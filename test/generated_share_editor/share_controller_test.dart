import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const content = ShareEditorContent(
    projectId: 'project',
    headline: 'Original headline',
    secondaryText: 'Original dare',
    ownerName: 'Alex',
    ownerHandle: 'alex',
    avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
    cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
    caption: 'Caption',
    publicLink: 'https://ptw.to/p/project',
  );

  test('value JSON preserves images, transforms, properties, and stickers', () {
    final value = ShareEditorValue(
      lookId: 'project_focus',
      backgroundId: 'project_cover',
      layerValues: const {
        'headline': 'Edited',
        'avatar': ShareImageValue.asset('avatar.png'),
      },
      transforms: const {
        'headline': ShareLayerTransform(
          x: 12,
          y: 20,
          width: 300,
          height: 200,
          rotation: 0.2,
        ),
      },
      stickers: const [
        ShareStickerValue(
          instanceId: 'one',
          stickerId: 'cheering_blob',
          centerX: 0.5,
          centerY: 0.4,
          scale: 0.25,
          rotation: 0.1,
        ),
      ],
      propertyOverrides: const {
        'headline': {'fontSize': 48.0},
      },
    );

    final restored = ShareEditorValue.fromJson(
      jsonDecode(jsonEncode(value.toJson())) as Map<String, dynamic>,
    );

    expect(restored.toJson(), value.toJson());
    expect(restored.layerValues['avatar'], isA<ShareImageValue>());
  });

  test(
    'controllers enforce hidden, locked, ranges, and sticker capabilities',
    () async {
      final source = (await ShareThemeBundle.loadAsset()).toJson();
      final layers =
          (source['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
      final headline = layers.singleWhere((item) => item['id'] == 'headline');
      final controls =
          (headline['controls'] as List<dynamic>).cast<Map<String, dynamic>>();
      controls.singleWhere((item) => item['id'] == 'edit')['access'] = {
        'mode': 'premiumVisible',
        'entitlementKey': 'pro_text',
      };
      controls.singleWhere((item) => item['id'] == 'fontSize')['access'] = {
        'mode': 'premiumHidden',
        'entitlementKey': 'pro_style',
      };
      final stickers =
          (source['stickers'] as List<dynamic>).cast<Map<String, dynamic>>();
      stickers.first['canRotate'] = false;
      final theme = ShareThemeConfig.fromJson(source);
      final free = ShareEditorController(theme: theme, content: content);

      expect(free.controlAccess('headline', 'edit'), ShareAccessState.locked);
      expect(
        free.controlAccess('headline', 'fontSize'),
        ShareAccessState.hidden,
      );
      expect(free.updateLayerValue('headline', 'Blocked'), isFalse);
      expect(free.updateLayerProperty('headline', 'fontSize', 60), isFalse);
      expect(free.addSticker(theme.stickers.first.id), isTrue);
      final sticker = free.value.stickers.single;
      expect(free.updateSticker(sticker.instanceId, rotation: 1), isFalse);
      free.dispose();

      final premium = ShareEditorController(
        theme: theme,
        content: content,
        entitlements: (_) => true,
      );
      expect(premium.updateLayerValue('headline', 'Premium edit'), isTrue);
      expect(premium.updateLayerProperty('headline', 'fontSize', 999), isTrue);
      expect(premium.effectiveStyle('headline')['fontSize'], 72.0);
      premium.dispose();
    },
  );

  test(
    'switching looks keeps user content while applying look defaults',
    () async {
      final theme = await ShareThemeBundle.loadAsset();
      final controller = ShareEditorController(theme: theme, content: content);
      const replacement = ShareImageValue.asset('replacement.png');
      expect(controller.updateLayerValue('headline', 'Keep this'), isTrue);
      expect(controller.updateLayerValue('avatar', replacement), isTrue);

      expect(controller.selectLook('candy_hype'), isTrue);

      expect(controller.layerValue('headline'), 'Keep this');
      expect(controller.layerValue('avatar'), same(replacement));
      expect(controller.value.backgroundId, 'gradient_candy');
      expect(controller.value.stickers.single.stickerId, 'cheering_blob');
      controller.dispose();
    },
  );

  test('invalid saved compositions are rejected before use', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final invalid = ShareEditorValue(
      lookId: theme.defaultLookId,
      backgroundId: theme.defaultBackgroundId,
      layerValues: const {},
      transforms: const {
        'headline': ShareLayerTransform(x: -1, y: 0, width: 20, height: 20),
      },
      stickers: const [],
    );
    expect(
      () => ShareEditorController(
        theme: theme,
        content: content,
        initialValue: invalid,
      ),
      throwsFormatException,
    );
  });
}
