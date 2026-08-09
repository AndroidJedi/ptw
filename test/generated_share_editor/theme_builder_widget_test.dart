import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/share_theme_builder_app.dart';
import 'package:ptw/features/share_theme_builder/theme_builder_controller.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('desktop builder exposes panes, premium preview, and nudging', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('headline');
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('LOOKS'), findsOneWidget);
    expect(find.text('LAYERS'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('builder_inspector_scroll')),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('builder_generate_zip')), findsOneWidget);

    final before = controller.editingLayer!.transform.x;
    await tester.tap(
      find.byKey(const ValueKey('builder_canvas_layer_headline')),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pump();
    expect(controller.editingLayer!.transform.x, before + 1);

    await tester.tap(find.text('Premium').first);
    await tester.pump();
    expect(controller.previewPremium, isTrue);
  });

  testWidgets('grid controls and sticker previews are visible', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller =
        ThemeBuilderController(await ShareThemeBundle.loadAsset())
          ..selectLook('candy_hype')
          ..selectLayer('stickers');
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('builder_canvas_grid')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('builder_sticker_workspace_inspector')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('builder_sticker_thumbnail_cheering_blob')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('builder_canvas_sticker_preset_candy_heart')),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const ValueKey('builder_canvas_sticker_preset_candy_heart')),
    );
    await tester.pump();
    expect(controller.selectedLookStickerId, 'preset_candy_heart');
    expect(
      find.byKey(
        const ValueKey('builder_transform_sticker_preset_candy_heart'),
      ),
      findsOneWidget,
    );
    final stickerBefore =
        controller.selectedLook.defaultStickers.single.centerX;
    controller.updateGrid(snap: false);
    await tester.drag(
      find.byKey(const ValueKey('builder_canvas_sticker_preset_candy_heart')),
      const Offset(24, 0),
    );
    await tester.pump();
    expect(
      controller.selectedLook.defaultStickers.single.centerX,
      greaterThan(stickerBefore),
    );

    controller.selectLayer('stickers');
    await tester.pump();
    final countBefore = controller.selectedLook.defaultStickers.length;
    await tester.tap(
      find.byKey(const ValueKey('builder_add_sticker_victory_hand')),
    );
    await tester.pump();
    expect(controller.selectedLook.defaultStickers, hasLength(countBefore + 1));
    expect(
      controller.selectedLook.defaultStickers.last.stickerId,
      'victory_hand',
    );

    await tester.tap(find.byKey(const ValueKey('builder_grid_toggle')));
    await tester.pump();
    expect(controller.showGrid, isFalse);
    expect(find.byKey(const ValueKey('builder_canvas_grid')), findsNothing);
  });

  testWidgets('editor settings repaint immediately and preview hides guides', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('avatar');
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Template label'), findsNothing);
    expect(find.text('Supports comparison'), findsNothing);
    expect(find.text('Appearance'), findsOneWidget);

    await tester.tap(find.text('Visible'));
    await tester.pump();
    expect(controller.editingLayer!.visible, isFalse);
    expect(
      find.byKey(const ValueKey('builder_canvas_layer_avatar')),
      findsNothing,
    );
    await tester.tap(find.text('Visible'));
    await tester.pump();
    expect(controller.editingLayer!.visible, isTrue);

    expect(find.byKey(const ValueKey('builder_canvas_grid')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('share_safe_zone_overlay')),
      findsOneWidget,
    );
    await tester.tap(find.text('Preview').first);
    await tester.pump();
    expect(controller.previewOnly, isTrue);
    expect(find.byKey(const ValueKey('builder_canvas_grid')), findsNothing);
    expect(find.byKey(const ValueKey('share_safe_zone_overlay')), findsNothing);
    expect(
      find.byKey(const ValueKey('builder_canvas_layer_headline')),
      findsNothing,
    );

    await tester.tap(find.text('Edit').first);
    await tester.pump();
    expect(controller.previewOnly, isFalse);
    expect(
      find.byKey(const ValueKey('builder_canvas_layer_headline')),
      findsOneWidget,
    );
  });

  testWidgets('avatar image and editing frame stay aligned while dragging', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller =
        ThemeBuilderController(await ShareThemeBundle.loadAsset())
          ..setMode(ThemeBuilderMode.production)
          ..selectLayer('avatar');
    controller.updateSelectedTransform(
      controller.editingLayer!.transform.copyWith(y: 210),
    );
    controller
      ..setMode(ThemeBuilderMode.explore)
      ..updateGrid(snap: false);
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    final frame = find.byKey(const ValueKey('builder_canvas_layer_avatar'));
    final renderedAvatar =
        find
            .descendant(
              of: find.byKey(const ValueKey('builder_live_renderer')),
              matching: find.byKey(const ValueKey('share_layer_avatar')),
            )
            .first;
    expect(frame, findsOneWidget);
    expect(renderedAvatar, findsOneWidget);
    var framePosition = tester.getTopLeft(frame);
    var avatarPosition = tester.getTopLeft(renderedAvatar);
    expect(framePosition.dx, closeTo(avatarPosition.dx, 2));
    expect(framePosition.dy, closeTo(avatarPosition.dy, 2));

    final logicalYBefore = controller.editingLayer!.transform.y;
    final themeBeforeGesture = controller.theme;
    final gesture = await tester.startGesture(tester.getCenter(frame));
    await gesture.moveBy(const Offset(0, 24));
    await tester.pump();
    await gesture.moveBy(const Offset(0, 24));
    await tester.pump();
    expect(identical(controller.theme, themeBeforeGesture), isTrue);
    expect(controller.editingLayer!.transform.y, greaterThan(logicalYBefore));
    framePosition = tester.getTopLeft(frame);
    avatarPosition = tester.getTopLeft(renderedAvatar);
    expect(framePosition.dx, closeTo(avatarPosition.dx, 2));
    expect(framePosition.dy, closeTo(avatarPosition.dy, 2));
    await gesture.up();
    await tester.pump();
    expect(identical(controller.theme, themeBeforeGesture), isFalse);
  });

  testWidgets('inspector shows and edits only selected component fields', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('headline');
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    final inspector =
        find
            .descendant(
              of: find.byKey(const ValueKey('builder_inspector_scroll')),
              matching: find.byType(Scrollable),
            )
            .first;
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('layer_section_headline')),
      250,
      scrollable: inspector,
    );
    expect(find.text('Template label'), findsNothing);
    expect(find.text('Runtime permissions'), findsNothing);

    final x = _numberField('X');
    await tester.ensureVisible(x);
    await tester.enterText(x, '37');
    await tester.pump();
    expect(controller.selectedLayer!.transform.x, 37);

    for (final type in const ['image', 'asset', 'shape']) {
      controller.addLayer(type);
      await tester.pump();
      final newLayerId = controller.selectedLayerId;
      final overlay = find.byKey(ValueKey('builder_canvas_layer_$newLayerId'));
      expect(overlay, findsOneWidget, reason: type);
      controller.selectLayer(newLayerId);
      await tester.pump();
      expect(controller.selectedLayerId, newLayerId, reason: type);
      final before = controller.selectedLayer!.transform.x;
      controller.updateGrid(snap: false);
      await tester.drag(overlay, const Offset(24, 0));
      await tester.pump();
      expect(
        controller.selectedLayer!.transform.x,
        greaterThan(before),
        reason: type,
      );
    }
  });

  testWidgets('looks, images, and fonts are selected from visual previews', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    );
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('builder_look_visual_picker')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('builder_visual_picker_grid_Look')),
      findsOneWidget,
    );
    await tester.tap(
      find.byKey(const ValueKey('builder_visual_option_hot_dare')),
    );
    await tester.pumpAndSettle();
    expect(controller.selectedLookId, 'hot_dare');

    final inspector =
        find
            .descendant(
              of: find.byKey(const ValueKey('builder_inspector_scroll')),
              matching: find.byType(Scrollable),
            )
            .first;
    controller.addLayer('image');
    await tester.pump();
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('builder_image_asset_visual_picker')),
      300,
      scrollable: inspector,
    );
    await tester.ensureVisible(
      find.byKey(const ValueKey('builder_image_asset_visual_picker')),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey('builder_image_asset_visual_picker')),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('builder_visual_option_cheering_blob')),
      findsOneWidget,
    );
    await tester.tap(
      find.byKey(const ValueKey('builder_visual_option_cheering_blob')),
    );
    await tester.pumpAndSettle();
    expect(controller.selectedLayer!.style['assetId'], 'cheering_blob');

    controller.selectLayer('headline');
    await tester.pump();
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('builder_font_visual_picker')),
      300,
      scrollable: inspector,
    );
    await tester.ensureVisible(
      find.byKey(const ValueKey('builder_font_visual_picker')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('builder_font_visual_picker')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('builder_visual_option_PtwRoboto')),
      findsOneWidget,
    );
    await tester.tap(
      find.byKey(const ValueKey('builder_visual_option_PtwRoboto')),
    );
    await tester.pumpAndSettle();
    expect(controller.selectedLayer!.style['fontFamily'], 'PtwRoboto');
  });
}

Finder _numberField(String label) =>
    find.byKey(ValueKey('builder_number_field_$label')).first;
