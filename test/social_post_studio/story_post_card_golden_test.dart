import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/social_post_studio/story_post_card.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemeStickerCatalog catalog;

  setUpAll(() async {
    catalog = await loadMemeStickerCatalog();
    final textFonts =
        FontLoader('PtwRoboto')
          ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
          ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf'));
    final stickerFonts = FontLoader('PtwLilitaOne')
      ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'));
    await Future.wait([textFonts.load(), stickerFonts.load()]);
  });

  testWidgets('default and decorated Story cards match the visual baseline', (
    tester,
  ) async {
    debugPaintBaselinesEnabled = false;
    await tester.binding.setSurfaceSize(const Size(760, 680));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final defaultDraft = SocialPostDraft(
      message: "tell me why\ni won't.",
      avatar: const StudioImageRef.asset('assets/images/users/alex.jpg'),
      backgroundId: 'gradient_night',
      stickers: const [],
    );
    final decoratedDraft = SocialPostDraft(
      message: 'make your doubt useful.',
      avatar: const StudioImageRef.asset('assets/images/users/maya.jpg'),
      backgroundId: 'gradient_hot',
      stickers: const [
        StickerPlacement(
          instanceId: 'one',
          stickerId: 'side_eye_orb',
          centerX: 0.8,
          centerY: 0.24,
          scale: 0.23,
          rotation: 0.18,
        ),
        StickerPlacement(
          instanceId: 'two',
          stickerId: 'cheering_blob',
          centerX: 0.2,
          centerY: 0.7,
          scale: 0.26,
          rotation: -0.14,
        ),
        StickerPlacement(
          instanceId: 'three',
          stickerId: 'dancing_flame',
          centerX: 0.78,
          centerY: 0.76,
          scale: 0.24,
          rotation: 0.2,
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          key: const ValueKey('studio_golden'),
          color: const Color(0xFF202027),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Row(
              children: [
                for (final draft in [defaultDraft, decoratedDraft]) ...[
                  SizedBox(
                    width: 360,
                    height: 640,
                    child: StoryPostCard(draft: draft, catalog: catalog),
                  ),
                  if (draft == defaultDraft) const SizedBox(width: 10),
                ],
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(find.byKey(const ValueKey('studio_golden')));
    await tester.runAsync(
      () => Future.wait([
        for (final asset in const [
          'assets/images/users/alex.jpg',
          'assets/images/users/maya.jpg',
          'assets/images/stickers/side_eye_orb.png',
          'assets/images/stickers/cheering_blob.png',
          'assets/images/stickers/dancing_flame.png',
        ])
          precacheImage(AssetImage(asset), context),
      ]),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byKey(const ValueKey('studio_golden')),
      matchesGoldenFile('../goldens/social_post_studio_cards.png'),
    );
  });
}
