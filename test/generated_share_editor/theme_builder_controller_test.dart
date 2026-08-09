import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/theme_builder_controller.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'builder edits base/look transforms and supports undo and redo',
    () async {
      final controller = ThemeBuilderController(
        await ShareThemeBundle.loadAsset(),
      );
      controller.selectLayer('headline');
      final base = controller.selectedLayer!.transform;
      controller.updateSelectedTransform(base.copyWith(x: base.x + 8));
      expect(controller.selectedLayer!.transform.x, base.x + 8);
      expect(controller.canUndo, isTrue);

      controller.undo();
      expect(controller.selectedLayer!.transform.x, base.x);
      controller.redo();
      expect(controller.selectedLayer!.transform.x, base.x + 8);

      controller.toggleLookOverrides(true);
      controller.updateSelectedTransform(base.copyWith(y: base.y + 12));
      expect(controller.selectedLayer!.transform.y, base.y);
      expect(controller.editingLayer!.transform.y, base.y + 12);

      controller.selectLook('project_focus');
      controller.addLookSticker('cheering_blob');
      final sticker = controller.selectedLook.defaultStickers.single;
      controller.updateLookSticker(sticker.instanceId, rotation: 0.4);
      expect(controller.selectedLook.defaultStickers.single.rotation, 0.4);
      controller.removeLookSticker(sticker.instanceId);
      expect(controller.selectedLook.defaultStickers, isEmpty);
      controller.dispose();
    },
  );

  test('builder imports atomically and embeds supported assets', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    );
    final before = ShareThemeBundle.toJsonString(controller.theme);
    expect(
      () => controller.replaceFromJson('{"schemaVersion":99}'),
      throwsA(anything),
    );
    expect(ShareThemeBundle.toJsonString(controller.theme), before);

    final assetId = await controller.addAsset(
      fileName: 'Brand Mark.PNG',
      mimeType: 'image/png',
      bytes: Uint8List.fromList(const [137, 80, 78, 71]),
      kind: 'image',
    );
    final asset = controller.theme.assets.last;
    expect(assetId, 'brand_mark_png');
    expect(asset.id, 'brand_mark_png');
    expect(base64Decode(asset.data!), const [137, 80, 78, 71]);
    controller.addPhotoBackground(assetId, label: 'Brand portrait');
    final background = controller.theme.backgrounds.last;
    expect(background.label, 'Brand portrait');
    expect(background.kind, 'image');
    expect(background.properties['assetId'], assetId);
    controller.dispose();
  });

  test('sticker drag deltas accumulate across pointer updates', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLook('candy_hype');
    addTearDown(controller.dispose);
    final workspace =
        controller.theme.layers
            .firstWhere((layer) => layer.type == 'stickerWorkspace')
            .transform;
    final before = controller.selectedLook.defaultStickers.single.centerX;

    controller.moveLookStickerBy(
      'preset_candy_heart',
      deltaX: 18,
      deltaY: 0,
      workspace: workspace,
    );
    controller.moveLookStickerBy(
      'preset_candy_heart',
      deltaX: 18,
      deltaY: 0,
      workspace: workspace,
    );

    expect(
      controller.selectedLook.defaultStickers.single.centerX,
      closeTo(before + 36 / workspace.width, 0.0001),
    );
  });

  test('layer gestures preview freely and commit one undo step', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('avatar');
    addTearDown(controller.dispose);
    controller.updateGrid(snap: false);
    final initialTheme = controller.theme;
    final initial = controller.editingLayer!.transform;
    var notifications = 0;
    controller.addListener(() => notifications++);

    controller.beginSelectedLayerTransform();
    for (var index = 0; index < 60; index++) {
      controller.moveSelectedLayerBy(deltaX: 1, deltaY: 0.5);
    }

    expect(identical(controller.theme, initialTheme), isTrue);
    expect(controller.canUndo, isFalse);
    expect(notifications, 0);
    expect(controller.editingLayer!.transform.x, closeTo(initial.x + 60, 0.01));
    expect(controller.editingLayer!.transform.y, closeTo(initial.y + 30, 0.01));

    controller.finishSelectedLayerTransform();
    expect(identical(controller.theme, initialTheme), isFalse);
    expect(controller.canUndo, isTrue);
    expect(notifications, 1);
    expect(
      controller.selectedLayer!.transform.x,
      closeTo(initial.x + 60, 0.01),
    );

    controller.undo();
    expect(controller.editingLayer!.transform.x, initial.x);
    expect(controller.canUndo, isFalse);
  });

  test('cancelled layer gesture discards its live draft', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('avatar');
    addTearDown(controller.dispose);
    controller.updateGrid(snap: false);
    final initialTheme = controller.theme;
    final initial = controller.editingLayer!.transform;
    var notifications = 0;
    controller.addListener(() => notifications++);

    controller.beginSelectedLayerTransform();
    controller.moveSelectedLayerBy(deltaX: 80, deltaY: 20);
    expect(controller.editingLayer!.transform.x, initial.x + 80);
    controller.cancelSelectedLayerTransform();

    expect(identical(controller.theme, initialTheme), isTrue);
    expect(controller.editingLayer!.transform.x, initial.x);
    expect(controller.canUndo, isFalse);
    expect(notifications, 0);
  });

  test('center-angle rotation magnetically snaps to quarter turns', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('headline');
    addTearDown(controller.dispose);
    controller.updateGrid(snap: false);
    final initialRotation = controller.editingLayer!.transform.rotation;

    controller.beginSelectedLayerRotation(0);
    controller.rotateSelectedLayerTo(math.pi / 2 + math.pi / 60);
    expect(
      controller.editingLayer!.transform.rotation,
      closeTo(initialRotation + math.pi / 2, 0.0001),
    );

    controller.rotateSelectedLayerTo(math.pi / 2 + math.pi / 20);
    expect(
      controller.editingLayer!.transform.rotation,
      closeTo(initialRotation + math.pi / 2 + math.pi / 20, 0.0001),
    );
    controller.finishSelectedLayerTransform();
  });

  test('sticker and style gestures each commit once', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLook('candy_hype');
    addTearDown(controller.dispose);
    controller.updateGrid(snap: false);
    final sticker = controller.selectedLook.defaultStickers.single;
    controller.selectLookSticker(sticker.instanceId);
    final workspace =
        controller.theme.layers
            .firstWhere((layer) => layer.type == 'stickerWorkspace')
            .transform;
    var notifications = 0;
    controller.addListener(() => notifications++);
    final themeBeforeSticker = controller.theme;

    controller.beginLookStickerTransform(sticker.instanceId);
    for (var index = 0; index < 50; index++) {
      controller.moveLookStickerBy(
        sticker.instanceId,
        deltaX: 1,
        deltaY: 0,
        workspace: workspace,
      );
    }
    expect(identical(controller.theme, themeBeforeSticker), isTrue);
    expect(notifications, 0);
    controller.finishLookStickerTransform(workspace: workspace);
    expect(notifications, 1);
    expect(controller.canUndo, isTrue);

    controller.selectLayer('avatar');
    notifications = 0;
    final themeBeforeStyle = controller.theme;
    controller.beginSelectedLayerStyleEdit();
    for (var index = 0; index < 50; index++) {
      controller.previewSelectedLayerStyle('blur', index / 2);
    }
    expect(identical(controller.theme, themeBeforeStyle), isTrue);
    expect(notifications, 0);
    expect(controller.editingLayer!.style['blur'], 24.5);
    controller.finishSelectedLayerStyleEdit();
    expect(notifications, 1);
    expect(controller.editingLayer!.style['blur'], 24.5);
  });

  test('background blur gestures preview without theme churn', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    );
    addTearDown(controller.dispose);
    var notifications = 0;
    controller.addListener(() => notifications++);
    final themeBeforeTreatment = controller.theme;
    final treatment = controller.selectedLook.backgroundTreatment;

    controller.beginBackgroundTreatmentEdit();
    for (var index = 0; index < 40; index++) {
      controller.previewBackgroundTreatment(
        treatment.copyWith(blur: index / 2),
      );
    }
    expect(identical(controller.theme, themeBeforeTreatment), isTrue);
    expect(notifications, 0);
    controller.finishBackgroundTreatmentEdit();
    expect(notifications, 1);
    expect(controller.selectedLook.backgroundTreatment.blur, 19.5);

    notifications = 0;
    final background = controller.theme.background(
      controller.selectedLook.backgroundId ??
          controller.theme.defaultBackgroundId,
    );
    final themeBeforeBackground = controller.theme;
    controller.beginBackgroundEdit();
    for (var index = 0; index < 40; index++) {
      controller.previewBackground(
        ShareBackgroundConfig(
          id: background.id,
          label: background.label,
          kind: background.kind,
          properties: {...background.properties, 'blur': index / 2},
          access: background.access,
        ),
      );
    }
    expect(identical(controller.theme, themeBeforeBackground), isTrue);
    expect(notifications, 0);
    controller.finishBackgroundEdit();
    expect(notifications, 1);
    expect(controller.theme.background(background.id).properties['blur'], 19.5);
  });

  test(
    'layer dragging accumulates and snaps to centers and safe areas',
    () async {
      final controller = ThemeBuilderController(
        await ShareThemeBundle.loadAsset(),
      )..selectLayer('avatar');
      addTearDown(controller.dispose);
      final start = controller.editingLayer!.transform;

      controller.updateGrid(snap: false);
      controller.beginSelectedLayerTransform();
      controller.moveSelectedLayerBy(deltaX: 18, deltaY: 14);
      controller.moveSelectedLayerBy(deltaX: 18, deltaY: 14);
      final moved = controller.editingLayer!.transform;
      expect(moved.x, closeTo(start.x + 36, 0.001));
      expect(moved.y, closeTo(start.y + 28, 0.001));
      controller.finishSelectedLayerTransform();

      controller.updateGrid(snap: true);
      controller.updateSelectedTransform(start.copyWith(x: 100));
      controller.beginSelectedLayerTransform();
      controller.moveSelectedLayerBy(deltaX: 37, deltaY: 0);
      expect(
        controller.editingLayer!.transform.x + start.width / 2,
        controller.theme.canvas.width / 2,
      );

      controller.updateSelectedTransform(start.copyWith(x: 40));
      controller.beginSelectedLayerTransform();
      controller.moveSelectedLayerBy(deltaX: -17, deltaY: 0);
      expect(controller.editingLayer!.transform.x, 24);
    },
  );

  test('base edits stay synchronized with active template and look', () async {
    final controller =
        ThemeBuilderController(await ShareThemeBundle.loadAsset())
          ..setMode(ThemeBuilderMode.production)
          ..selectLayer('avatar');
    addTearDown(controller.dispose);
    final base = controller.selectedLayer!.transform;

    controller.updateSelectedTransform(base.copyWith(y: 210));
    expect(controller.editingLayer!.transform.y, 210);

    controller.setMode(ThemeBuilderMode.explore);
    controller.updateGrid(snap: false);
    controller.beginSelectedLayerTransform();
    controller.moveSelectedLayerBy(deltaX: 0, deltaY: 24);

    expect(controller.selectedLayer!.transform.y, base.y);
    expect(controller.editingLayer!.transform.y, 234);
    controller.finishSelectedLayerTransform();
    expect(controller.selectedLayer!.transform.y, 234);
    expect(
      controller.selectedTemplate.layerOverrides['avatar']?['transform'],
      isNull,
    );

    final preview =
        ShareEditorController(
            theme: controller.theme,
            content: const ShareEditorContent(
              projectId: 'preview',
              headline: 'Headline',
              secondaryText: 'Challenge',
              ownerName: 'Owner',
              ownerHandle: '@owner',
              avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
              cover: ShareImageValue.asset(
                'assets/images/backgrounds/startup.jpg',
              ),
              caption: 'Caption',
              publicLink: 'https://example.com',
            ),
          )
          ..selectLook(controller.selectedLookId)
          ..selectTemplate(controller.selectedTemplateId);
    addTearDown(preview.dispose);
    expect(preview.effectiveLayer('avatar').transform.y, 234);
  });

  test('template switches immediately synchronize visible layers', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectTemplate('hero_photo');
    addTearDown(controller.dispose);

    controller.updateSelectedTemplate(supportsComparison: true);
    expect(
      controller.selectedTemplate.layerOverrides['previous_media']!['visible'],
      isTrue,
    );
    expect(
      controller.selectedTemplate.layerOverrides['current_media']!['visible'],
      isTrue,
    );
    expect(controller.selectedTemplate.supportedMediaCount, 2);

    controller.updateSelectedTemplate(supportsProof: true);
    expect(
      controller.selectedTemplate.layerOverrides['progress_value']!['visible'],
      isTrue,
    );
    expect(
      controller.selectedTemplate.layerOverrides['metric_value']!['visible'],
      isTrue,
    );

    controller.updateSelectedTemplate(
      optionalContentRoles: {
        ...controller.selectedTemplate.optionalContentRoles,
        ShareSemanticRole.currentMedia,
      },
    );
    expect(
      controller.selectedTemplate.layerOverrides['current_media']!['visible'],
      isTrue,
    );
    controller.updateSelectedTemplate(
      optionalContentRoles: {
        ...controller.selectedTemplate.optionalContentRoles,
      }..remove(ShareSemanticRole.currentMedia),
    );
    expect(
      controller.selectedTemplate.layerOverrides['current_media']!['visible'],
      isFalse,
    );
  });

  test('grid snapping applies to layers and default stickers', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    );
    addTearDown(controller.dispose);

    controller
      ..selectLayer('headline')
      ..updateGrid(size: 20);
    final layer = controller.editingLayer!;
    controller.updateSelectedTransform(
      layer.transform.copyWith(x: 37, y: 43, width: 293, height: 217),
      useGrid: true,
    );
    expect(controller.editingLayer!.transform.x, 40);
    expect(controller.editingLayer!.transform.y, 40);
    expect(controller.editingLayer!.transform.width, 300);
    expect(controller.editingLayer!.transform.height, 220);

    controller
      ..selectLook('candy_hype')
      ..updateLookSticker(
        'preset_candy_heart',
        centerX: 0.713,
        centerY: 0.337,
        scale: 0.277,
      )
      ..snapLookSticker('preset_candy_heart');
    final sticker = controller.selectedLook.defaultStickers.single;
    expect(sticker.centerX, closeTo(0.7222, 0.001));
    expect(sticker.centerY, closeTo(0.34375, 0.001));
    expect(sticker.scale, closeTo(0.2778, 0.001));
  });

  test('builder updates the exported post corner radius', () async {
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    );
    addTearDown(controller.dispose);

    controller.updateMetadata(cornerRadius: 28);
    expect(controller.theme.canvas.cornerRadius, 28);
    final json =
        jsonDecode(ShareThemeBundle.toJsonString(controller.theme))
            as Map<String, dynamic>;
    expect((json['canvas'] as Map<String, dynamic>)['cornerRadius'], 28);
  });

  test(
    'production mode edits template structure without changing base',
    () async {
      final controller = ThemeBuilderController(
        await ShareThemeBundle.loadAsset(),
      );
      addTearDown(controller.dispose);
      controller
        ..setMode(ThemeBuilderMode.production)
        ..selectTemplate('comparison')
        ..selectLayer('headline');
      final base = controller.selectedLayer!.transform;

      controller.updateSelectedTransform(base.copyWith(y: 430));

      expect(controller.selectedLayer!.transform.y, base.y);
      expect(controller.editingLayer!.transform.y, 390);
      expect(
        controller.selectedTemplate.layerOverrides['headline']!['transform'],
        isA<Map<String, dynamic>>(),
      );

      controller.updateSelectedVisibility(false);
      expect(controller.selectedLayer!.visible, isTrue);
      expect(controller.editingLayer!.visible, isFalse);
    },
  );
}
