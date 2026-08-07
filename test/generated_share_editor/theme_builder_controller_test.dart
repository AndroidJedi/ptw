import 'dart:convert';
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

    await controller.addAsset(
      fileName: 'Brand Mark.PNG',
      mimeType: 'image/png',
      bytes: Uint8List.fromList(const [137, 80, 78, 71]),
      kind: 'image',
    );
    final asset = controller.theme.assets.last;
    expect(asset.id, 'brand_mark_png');
    expect(base64Decode(asset.data!), const [137, 80, 78, 71]);
    controller.dispose();
  });
}
