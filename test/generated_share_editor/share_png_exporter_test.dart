import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('generated renderer exports configured PNG dimensions', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(400, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final base = await ShareThemeBundle.loadAsset();
    final source = base.toJson();
    final canvas =
        Map<String, dynamic>.from(source['canvas'] as Map)
          ..['outputWidth'] = 720
          ..['outputHeight'] = 1280;
    source['canvas'] = canvas;
    final theme = ShareThemeConfig.fromJson(source);
    const content = ShareEditorContent(
      projectId: 'project',
      headline: 'Export this Story',
      secondaryText: 'At the configured size',
      ownerName: 'Alex',
      ownerHandle: 'alex',
      avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
      cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
      caption: 'Caption',
      publicLink: 'https://ptw.to/p/project',
    );
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);
    final boundaryKey = GlobalKey();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: RepaintBoundary(
              key: boundaryKey,
              child: SizedBox(
                width: theme.canvas.width,
                height: theme.canvas.height,
                child: GeneratedShareRenderer(
                  theme: theme,
                  content: content,
                  value: controller.value,
                  showSelection: false,
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(GeneratedShareRenderer));
    await tester.runAsync(
      () => Future.wait([
        precacheImage(
          const AssetImage('assets/images/users/alex.jpg'),
          context,
        ),
        precacheImage(
          const AssetImage('assets/images/backgrounds/startup.jpg'),
          context,
        ),
      ]),
    );
    await tester.pumpAndSettle();

    final asset = await tester.runAsync(
      () => const SharePngExporter().capture(
        boundaryKey: boundaryKey,
        theme: theme,
        fileName: 'configured.png',
      ),
    );
    expect(asset!.width, 720);
    expect(asset.height, 1280);
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
    expect(dimensions, const Size(720, 1280));
  });

  testWidgets('photo crop, treatment, fonts, and decor export at Story size', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(400, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final theme = await ShareThemeBundle.loadAsset();
    const content = ShareEditorContent(
      projectId: 'personal_project',
      headline: 'This one is personal',
      secondaryText: 'Watch me follow through',
      ownerName: 'Alex',
      ownerHandle: 'alex',
      avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
      cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
      caption: 'Caption',
      publicLink: 'https://ptw.to/p/personal_project',
    );
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);
    controller
      ..replaceBackgroundImage(
        const ShareImageValue.asset('assets/images/backgrounds/creative.jpg'),
      )
      ..updateBackgroundCrop(alignmentX: 0.3, alignmentY: -0.25, zoom: 1.8)
      ..selectLook('candy_hype')
      ..addOverlay(
        const ShareImageValue.asset(
          'assets/images/decorations/doodle_heart.png',
        ),
      );
    final boundaryKey = GlobalKey();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: RepaintBoundary(
              key: boundaryKey,
              child: SizedBox(
                width: theme.canvas.width,
                height: theme.canvas.height,
                child: GeneratedShareRenderer(
                  theme: theme,
                  content: content,
                  value: controller.value,
                  showSelection: false,
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(GeneratedShareRenderer));
    await tester.runAsync(
      () => Future.wait([
        for (final path in [
          'assets/images/users/alex.jpg',
          'assets/images/backgrounds/creative.jpg',
          'assets/images/decorations/candy_heart.png',
          'assets/images/decorations/doodle_heart.png',
        ])
          precacheImage(AssetImage(path), context),
      ]),
    );
    await tester.pumpAndSettle();

    final asset = await tester.runAsync(
      () => const SharePngExporter().capture(
        boundaryKey: boundaryKey,
        theme: theme,
        fileName: 'personal.png',
      ),
    );

    expect(asset!.width, 1080);
    expect(asset.height, 1920);
    expect(asset.fileName, 'personal.png');
    expect(asset.bytes.take(8), const [137, 80, 78, 71, 13, 10, 26, 10]);
  });
}
