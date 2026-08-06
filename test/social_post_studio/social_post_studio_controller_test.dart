import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/social_post_studio/social_post_studio_controller.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemeStickerCatalog catalog;

  setUpAll(() async {
    catalog = await loadMemeStickerCatalog();
  });

  SocialPostStudioController createController() =>
      SocialPostStudioController(catalog: catalog);

  test('adds no more than three stickers at normalized safe anchors', () {
    final controller = createController();

    expect(controller.addSticker('cheering_blob'), isTrue);
    expect(controller.addSticker('victory_hand'), isTrue);
    expect(controller.addSticker('turbo_rocket'), isTrue);
    expect(controller.addSticker('trophy_gremlin'), isFalse);

    expect(controller.draft.stickers, hasLength(3));
    expect(controller.draft.stickers[0].centerX, 0.78);
    expect(controller.draft.stickers[1].centerY, 0.72);
    expect(controller.draft.stickers[2].centerY, 0.76);
    expect(controller.canAddSticker, isFalse);
  });

  test('placement updates clamp bounds, scale, and normalize rotation', () {
    final controller = createController()..addSticker('cheering_blob');
    final id = controller.selectedStickerId!;

    controller.updatePlacement(
      id,
      centerX: -2,
      centerY: 4,
      scale: 2,
      rotation: math.pi * 5,
    );

    final placement = controller.selectedPlacement!;
    expect(placement.centerX, 0);
    expect(placement.centerY, 1);
    expect(placement.scale, StickerPlacement.maximumScale);
    expect(placement.rotation.abs(), closeTo(math.pi, 0.0001));
  });

  test('duplicates, reorders, removes, and resets layers', () {
    final controller = createController()..addSticker('cheering_blob');
    final originalId = controller.selectedStickerId!;

    expect(controller.duplicateSelected(), isTrue);
    final duplicateId = controller.selectedStickerId!;
    expect(duplicateId, isNot(originalId));
    controller.moveSelectedBackward();
    expect(controller.draft.stickers.first.instanceId, duplicateId);
    controller.moveSelectedForward();
    expect(controller.draft.stickers.last.instanceId, duplicateId);
    controller.removeSelected();
    expect(controller.draft.stickers.single.instanceId, originalId);

    controller.updateMessage('changed');
    controller.selectBackground('gradient_hot');
    controller.reset();
    expect(controller.draft.message, "tell me why\ni won't.");
    expect(controller.draft.backgroundId, 'startup');
    expect(controller.draft.stickers, isEmpty);
    expect(controller.selectedStickerId, isNull);
  });

  test('message and avatar limits are enforced by the controller', () {
    final controller = createController();
    controller.updateMessage(List.filled(120, 'x').join());
    expect(controller.draft.message, hasLength(100));
    expect(() => controller.setAvatarBytes(Uint8List(0)), throwsArgumentError);
    expect(
      () => controller.setAvatarBytes(
        Uint8List(SocialPostStudioController.maximumAvatarBytes + 1),
      ),
      throwsArgumentError,
    );
  });

  test('category filtering returns only the selected collection', () {
    final controller = createController();
    controller.selectCategory(MemeStickerCategory.chaos);

    expect(controller.visibleStickers, hasLength(4));
    expect(
      controller.visibleStickers,
      everyElement(
        isA<MemeStickerDefinition>().having(
          (item) => item.category,
          'category',
          MemeStickerCategory.chaos,
        ),
      ),
    );
  });
}
