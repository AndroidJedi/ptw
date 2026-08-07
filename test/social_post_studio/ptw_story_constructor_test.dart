import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/features/social_post_studio/ptw_story_composer.dart';
import 'package:ptw/features/social_post_studio/ptw_story_constructor_controller.dart';
import 'package:ptw/features/social_post_studio/story_look_presets.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_story_composition.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemeStickerCatalog catalog;
  final now = DateTime(2026, 8, 6, 12);

  setUpAll(() async {
    catalog = await loadMemeStickerCatalog();
  });

  PtwProject project({String id = 'project_viral'}) => PtwProject(
    id: id,
    ownerId: 'user_alex',
    ownerName: 'Alex',
    ownerHandle: 'alexbuilds',
    ownerAvatarAsset: 'assets/images/users/alex.jpg',
    goal: 'Ship the idea everyone says is too ambitious',
    image: const PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
    primaryColor: 0xFFF4066E,
    status: PtwProjectStatus.active,
    createdAt: now,
  );

  PtwStoryComposition composition({ShareEvent event = ShareEvent.manual}) =>
      const PtwStoryComposer().create(
        project: project(),
        event: event,
        momentId: 'moment_1',
        now: now,
      );

  test('composer is deterministic for the same project and moment', () {
    final first = composition();
    final second = composition();
    final different = const PtwStoryComposer().create(
      project: project(),
      event: ShareEvent.manual,
      momentId: 'moment_2',
      now: now,
    );

    expect(first.lookId, second.lookId);
    expect(first.backgroundId, second.backgroundId);
    expect(
      first.stickers.map((item) => item.stickerId),
      second.stickers.map((item) => item.stickerId),
    );
    expect(
      PtwStoryLooks.indexForSeed('project_viral:moment_1'),
      isNot(PtwStoryLooks.indexForSeed('project_viral:moment_2')),
    );
    expect(different.momentId, 'moment_2');
  });

  test('context events produce the five short dares', () {
    const composer = PtwStoryComposer();
    expect(composer.dareFor(ShareEvent.manual), 'Think I won’t?');
    expect(composer.dareFor(ShareEvent.milestoneReached), 'Still doubting?');
    expect(
      composer.dareFor(ShareEvent.newSkeptic),
      'They said I won’t. Agree?',
    );
    expect(composer.dareFor(ShareEvent.newSupporter), 'They believe. Do you?');
    expect(composer.dareFor(ShareEvent.goalCompleted), 'I did it. What now?');
  });

  test('magic cycles six looks and Reset restores the generated Story', () {
    final initial = composition();
    final controller = PtwStoryConstructorController(
      catalog: catalog,
      initialComposition: initial,
      now: () => now,
    );
    addTearDown(controller.dispose);
    final seen = <String>{controller.composition.lookId};

    for (var index = 0; index < 6; index++) {
      controller.cycleLook();
      seen.add(controller.composition.lookId);
    }

    expect(seen, hasLength(6));
    expect(controller.hasChanges, isTrue);
    controller.reset();
    expect(controller.composition.toJson(), initial.toJson());
    expect(controller.hasChanges, isFalse);
  });

  test('editor limits text and stickers and clamps direct manipulation', () {
    final controller = PtwStoryConstructorController(
      catalog: catalog,
      initialComposition: PtwStoryLooks.apply(
        composition(),
        PtwStoryLooks.all.first,
        now,
      ),
      now: () => now,
    );
    addTearDown(controller.dispose);
    controller.updateText(
      headline: List.filled(100, 'x').join(),
      dare: List.filled(60, 'y').join(),
    );
    expect(controller.composition.headline, hasLength(90));
    expect(controller.composition.dare, hasLength(48));
    expect(controller.addSticker('cheering_blob'), isTrue);
    expect(controller.addSticker('side_eye_orb'), isTrue);
    expect(controller.addSticker('screaming_toaster'), isTrue);
    expect(controller.addSticker('trophy_gremlin'), isFalse);

    final id = controller.selectedStickerId!;
    controller.updateSticker(
      id,
      centerX: -4,
      centerY: 3,
      scale: 9,
      rotation: math.pi * 5,
    );
    final changed = controller.composition.stickers.last;
    expect(changed.centerX, 0.05);
    expect(changed.centerY, 0.95);
    expect(changed.scale, PtwStoryStickerPlacement.maximumScale);
    expect(changed.rotation.abs(), closeTo(math.pi, 0.0001));
  });

  test('composition serializes the exact editable Story', () {
    final source = composition().copyWith(
      headline: 'A share-only headline',
      dare: 'Try to stop me.',
      backgroundId: 'gradient_candy',
      lookId: 'custom',
      stickers: const [
        PtwStoryStickerPlacement(
          instanceId: 'one',
          stickerId: 'cheering_blob',
          centerX: 0.74,
          centerY: 0.28,
          scale: 0.24,
          rotation: 0.12,
        ),
      ],
    );

    final decoded = PtwStoryComposition.fromJson(source.toJson());
    expect(decoded.toJson(), source.toJson());
    expect(decoded.publicLink, 'https://ptw.to/p/project_viral');
  });
}
