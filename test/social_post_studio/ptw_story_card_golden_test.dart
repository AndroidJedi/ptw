import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/features/social_post_studio/ptw_story_asset_generator.dart';
import 'package:ptw/features/social_post_studio/ptw_story_card.dart';
import 'package:ptw/features/social_post_studio/ptw_story_composer.dart';
import 'package:ptw/features/social_post_studio/story_look_presets.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_story_composition.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemeStickerCatalog catalog;
  final now = DateTime(2026, 8, 6, 12);
  late PtwStoryComposition base;

  setUpAll(() async {
    catalog = await loadMemeStickerCatalog();
    final fonts = <FontLoader>[
      FontLoader('PtwRoboto')
        ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf')),
      FontLoader('PtwLilitaOne')
        ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf')),
    ];
    await Future.wait(fonts.map((loader) => loader.load()));
    base = const PtwStoryComposer().create(
      project: PtwProject(
        id: 'project_viral',
        ownerId: 'user_alex',
        ownerName: 'Alex',
        ownerHandle: 'alexbuilds',
        ownerAvatarAsset: 'assets/images/users/alex.jpg',
        goal: 'Launch a product nobody can ignore',
        image: PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
        primaryColor: 0xFFF4066E,
        status: PtwProjectStatus.active,
        createdAt: now,
      ),
      event: ShareEvent.challengeCreated,
      momentId: 'moment_1',
      now: now,
    );
  });

  testWidgets('all six looks and an edited Story match the mobile baseline', (
    tester,
  ) async {
    debugPaintBaselinesEnabled = false;
    await tester.binding.setSurfaceSize(const Size(820, 690));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final looks = [
      for (final preset in PtwStoryLooks.all)
        PtwStoryLooks.apply(base, preset, now),
      base.copyWith(
        headline: 'My own Story headline',
        dare: 'Who doubts this?',
        backgroundId: 'gradient_candy',
        lookId: 'custom',
        textTreatment: PtwStoryTextTreatment.candy,
        stickers: const [
          PtwStoryStickerPlacement(
            instanceId: 'one',
            stickerId: 'cheering_blob',
            centerX: 0.78,
            centerY: 0.25,
            scale: 0.24,
            rotation: 0.12,
          ),
          PtwStoryStickerPlacement(
            instanceId: 'two',
            stickerId: 'dancing_flame',
            centerX: 0.22,
            centerY: 0.72,
            scale: 0.22,
            rotation: -0.18,
          ),
        ],
      ),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          key: const ValueKey('ptw_story_looks_golden'),
          color: const Color(0xFF0E1423),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final composition in looks)
                  SizedBox(
                    width: 190,
                    height: 337.7778,
                    child: PtwStoryCard(
                      composition: composition,
                      catalog: catalog,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(
      find.byKey(const ValueKey('ptw_story_looks_golden')),
    );
    await tester.runAsync(
      () => Future.wait([
        for (final asset in [
          'assets/images/users/alex.jpg',
          'assets/images/backgrounds/startup.jpg',
          ...catalog.stickers.map((item) => item.assetPath),
        ])
          precacheImage(AssetImage(asset), context),
      ]),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byKey(const ValueKey('ptw_story_looks_golden')),
      matchesGoldenFile('../goldens/ptw_story_constructor_looks.png'),
    );
  });

  testWidgets('Story export is an exact 1080 by 1920 PNG', (tester) async {
    await tester.binding.setSurfaceSize(const Size(400, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final boundaryKey = GlobalKey();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: RepaintBoundary(
              key: boundaryKey,
              child: SizedBox.fromSize(
                size: PtwStoryCard.logicalSize,
                child: PtwStoryCard(composition: base, catalog: catalog),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final asset = await tester.runAsync(
      () => const PtwStoryAssetGenerator().capture(
        boundaryKey: boundaryKey,
        projectId: base.projectId,
      ),
    );
    expect(asset!.format, ShareFormat.story);
    expect(asset.bytes.take(8), const [137, 80, 78, 71, 13, 10, 26, 10]);
    final dimensions = await tester.runAsync(() async {
      final codec = await ui.instantiateImageCodec(asset.bytes);
      final frame = await codec.getNextFrame();
      final result = Size(
        frame.image.width.toDouble(),
        frame.image.height.toDouble(),
      );
      frame.image.dispose();
      codec.dispose();
      return result;
    });
    expect(dimensions, const Size(1080, 1920));
  });
}
