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
      templateId: 'comparison',
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
      backgroundEdit: const ShareBackgroundEdit(
        image: ShareImageValue.file('share/photo.webp'),
        alignmentX: 0.25,
        alignmentY: -0.4,
        zoom: 2.2,
        blur: 9,
        texture: ShareBackgroundTexture.grain,
        textureIntensity: 0.3,
      ),
      overlays: const [
        SharePlacedOverlayValue(
          instanceId: 'upload_1',
          image: ShareImageValue.file('share/decor.png'),
          centerX: 0.7,
          centerY: 0.2,
          scale: 0.22,
          rotation: 0.1,
        ),
      ],
    );

    final restored = ShareEditorValue.fromJson(
      jsonDecode(jsonEncode(value.toJson())) as Map<String, dynamic>,
    );

    expect(restored.toJson(), value.toJson());
    expect(restored.templateId, 'comparison');
    expect(restored.layerValues['avatar'], isA<ShareImageValue>());
  });

  test('legacy value JSON decodes photo and overlays as defaults', () {
    final legacy = <String, dynamic>{
      'lookId': 'project_focus',
      'backgroundId': 'project_cover',
      'layerValues': <String, dynamic>{},
      'transforms': <String, dynamic>{},
      'stickers': <dynamic>[],
    };

    final restored = ShareEditorValue.fromJson(legacy);

    expect(
      restored.backgroundEdit.toJson(),
      const ShareBackgroundEdit().toJson(),
    );
    expect(restored.overlays, isEmpty);
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
      const photo = ShareImageValue.file('share/replacement.webp');
      const upload = ShareImageValue.file('share/upload.png');
      expect(controller.updateLayerValue('headline', 'Keep this'), isTrue);
      expect(controller.updateLayerValue('avatar', replacement), isTrue);
      expect(controller.replaceBackgroundImage(photo), isTrue);
      expect(
        controller.updateBackgroundCrop(
          alignmentX: 0.35,
          alignmentY: -0.2,
          zoom: 2.4,
        ),
        isTrue,
      );
      expect(controller.addOverlay(upload), isTrue);
      expect(
        controller.updateLayerProperties('headline', const {
          'fontFamily': 'PtwRoboto',
          'fontSize': 44.0,
        }),
        isTrue,
      );

      expect(controller.selectLook('candy_hype'), isTrue);

      expect(controller.layerValue('headline'), 'Keep this');
      expect(controller.layerValue('avatar'), same(replacement));
      expect(controller.value.backgroundId, 'project_cover');
      expect(controller.value.backgroundEdit.image, same(photo));
      expect(controller.value.backgroundEdit.alignmentX, 0.35);
      expect(controller.value.backgroundEdit.alignmentY, -0.2);
      expect(controller.value.backgroundEdit.zoom, 2.4);
      expect(
        controller.value.backgroundEdit.texture,
        ShareBackgroundTexture.iridescent,
      );
      expect(controller.value.overlays.single.image, same(upload));
      expect(controller.value.stickers.single.stickerId, 'candy_heart');
      expect(controller.value.propertyOverrides, isEmpty);
      controller.dispose();
    },
  );

  test('photo edits clamp, restore the project photo, and reset', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    expect(
      controller.updateBackground(
        const ShareBackgroundEdit(
          image: ShareImageValue.file('share/photo.jpg'),
          alignmentX: 9,
          alignmentY: -9,
          zoom: 8,
          imageOpacity: 0,
          blur: 80,
        ),
      ),
      isTrue,
    );
    expect(controller.value.backgroundEdit.alignmentX, 1);
    expect(controller.value.backgroundEdit.alignmentY, -1);
    expect(controller.value.backgroundEdit.zoom, 4);
    expect(controller.value.backgroundEdit.imageOpacity, 0.2);
    expect(controller.value.backgroundEdit.blur, 30);

    expect(controller.useProjectBackground(), isTrue);
    expect(controller.value.backgroundEdit.image, isNull);
    expect(controller.value.backgroundEdit.zoom, 1);

    controller.reset();
    expect(controller.hasChanges, isFalse);
    expect(controller.value.toJson(), isNotEmpty);
    expect(
      controller.value.backgroundEdit,
      same(theme.look(theme.defaultLookId).backgroundTreatment),
    );
  });

  test('font and effect properties update atomically', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);
    var notifications = 0;
    controller.addListener(() => notifications++);

    expect(
      controller.updateLayerProperties('headline', const {
        'fontFamily': 'PtwPressStart2P',
        'fontSize': 54.0,
        'shadowX': 5.0,
        'shadowY': 5.0,
        'shadowColor': '#FFFFFF00',
      }),
      isTrue,
    );

    expect(notifications, 1);
    expect(
      controller.effectiveStyle('headline')['fontFamily'],
      'PtwPressStart2P',
    );
    expect(controller.effectiveStyle('headline')['shadowX'], 5.0);
  });

  test('catalog and uploaded decorations share the six-layer limit', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);
    expect(controller.selectLook('yellow_chaos'), isTrue);
    expect(controller.decorationCount, 4);

    expect(
      controller.addOverlay(const ShareImageValue.file('share/one.png')),
      isTrue,
    );
    expect(controller.addSticker('candy_heart'), isTrue);
    expect(controller.decorationCount, 6);
    expect(
      controller.addOverlay(const ShareImageValue.file('share/two.webp')),
      isFalse,
    );
    expect(controller.addSticker('sparkle'), isFalse);
  });

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

  test('invalid saved photo ranges are rejected before use', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final invalid = ShareEditorValue(
      lookId: theme.defaultLookId,
      backgroundId: theme.defaultBackgroundId,
      layerValues: const {},
      transforms: const {},
      stickers: const [],
      backgroundEdit: const ShareBackgroundEdit(zoom: 5),
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

  test('templates compose structure independently from looks', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    expect(controller.activeTemplate.id, 'hero_photo');
    expect(controller.effectiveLayer('previous_media').visible, isFalse);

    expect(controller.selectTemplate('comparison'), isTrue);
    expect(controller.value.templateId, 'comparison');
    expect(controller.effectiveLayer('previous_media').visible, isTrue);
    expect(controller.effectiveLayer('current_media').visible, isTrue);
    expect(controller.effectiveLayer('progress_value').visible, isFalse);

    expect(controller.selectLook('candy_hype'), isTrue);
    expect(controller.activeTemplate.id, 'comparison');
    expect(controller.effectiveLayer('previous_media').visible, isTrue);
  });

  test('runtime mode enforces exported template permissions', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(
      theme: theme,
      content: content,
      mode: ShareEditorMode.runtime,
    );
    addTearDown(controller.dispose);

    expect(controller.updateLayerValue('headline', 'Runtime edit'), isTrue);
    expect(controller.layerValue('headline'), 'Runtime edit');
    expect(controller.updateLayerTransform('headline', x: 60), isFalse);
    expect(controller.updateLayerProperty('headline', 'fontSize', 50), isFalse);
    expect(controller.selectLook('candy_hype'), isFalse);
    expect(controller.addSticker('candy_heart'), isFalse);
    expect(
      controller.replaceBackgroundImage(
        const ShareImageValue.file('share/runtime.jpg'),
      ),
      isTrue,
    );
    expect(controller.updateBackgroundCrop(zoom: 1.5), isTrue);

    expect(controller.selectTemplate('comparison'), isTrue);
    expect(
      controller.updateLayerValue(
        'previous_media',
        const ShareImageValue.file('share/before.jpg'),
      ),
      isTrue,
    );
    expect(
      controller.controlAccess('previous_media', 'edit'),
      ShareAccessState.available,
    );
    expect(
      controller.controlAccess('headline', 'fontSize'),
      ShareAccessState.hidden,
    );
  });
}
