import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_asset_generator.dart';
import 'package:ptw/features/share/share_card.dart';
import 'package:ptw/features/share/share_models.dart';

void main() {
  late ShareCatalog catalog;

  setUpAll(() async {
    final textFonts =
        FontLoader('PtwRoboto')
          ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
          ..addFont(rootBundle.load('assets/fonts/Roboto-Medium.ttf'))
          ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf'));
    final stickerFonts = FontLoader('PtwLilitaOne')
      ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'));
    final iconFonts = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await Future.wait([
      textFonts.load(),
      stickerFonts.load(),
      iconFonts.load(),
    ]);
    catalog = ShareCatalog.fromJson(
      jsonDecode(await rootBundle.loadString('assets/mock/share_content.json'))
          as Map<String, dynamic>,
    );
  });

  ShareCardData scenario(ShareTemplateType type) =>
      catalog.scenarios.singleWhere((item) => item.template == type);

  testWidgets('every template renders in every format without overflow', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1200, 2100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    for (final template in ShareTemplateType.values) {
      for (final format in ShareFormat.values) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Align(
                alignment: Alignment.topLeft,
                child: SizedBox(
                  width: 360,
                  height: 360 / format.aspectRatio,
                  child: ShareCard(data: scenario(template), format: format),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: '${template.name}/${format.name}',
        );
      }
    }
  });

  testWidgets('asset generator emits exact PNG dimensions', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1200, 2100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    for (final format in ShareFormat.values) {
      final boundaryKey = GlobalKey();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Align(
              alignment: Alignment.topLeft,
              child: RepaintBoundary(
                key: boundaryKey,
                child: SizedBox(
                  width: 360,
                  height: 360 / format.aspectRatio,
                  child: ShareCard(
                    data: scenario(ShareTemplateType.challenge),
                    format: format,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final asset = await tester.runAsync(
        () => const ShareAssetGenerator().capture(
          boundaryKey: boundaryKey,
          format: format,
          projectId: 'challenge_red_friday',
        ),
      );
      expect(asset!.bytes.take(8), const [137, 80, 78, 71, 13, 10, 26, 10]);
      final dimensions = await tester.runAsync(() async {
        final codec = await ui.instantiateImageCodec(asset.bytes);
        final frame = await codec.getNextFrame();
        final size = Size(
          frame.image.width.toDouble(),
          frame.image.height.toDouble(),
        );
        frame.image.dispose();
        codec.dispose();
        return size;
      });
      expect(
        dimensions,
        Size(format.width.toDouble(), format.height.toDouble()),
      );
    }
  });

  testWidgets('primary template compositions match the visual baseline', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(760, 1040));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          key: const ValueKey('share_golden'),
          color: const Color(0xFF202027),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final template in ShareTemplateType.values)
                  SizedBox(
                    width: 240,
                    height: 480,
                    child: ShareCard(
                      data: scenario(template),
                      format: ShareFormat.story,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byKey(const ValueKey('share_golden')),
      matchesGoldenFile('../goldens/share_templates.png'),
    );
  });
}
