import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    await Future.wait([
      (FontLoader('PtwRoboto')
            ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
            ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf')))
          .load(),
      (FontLoader(
        'PtwLilitaOne',
      )..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'))).load(),
      (FontLoader('PtwPressStart2P')..addFont(
        rootBundle.load('assets/fonts/PressStart2P-Regular.ttf'),
      )).load(),
      (FontLoader(
        'PtwRubikDirt',
      )..addFont(rootBundle.load('assets/fonts/RubikDirt-Regular.ttf'))).load(),
    ]);
  });

  testWidgets('five photo-first looks use the same personal photo', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(956, 336));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final theme = await ShareThemeBundle.loadAsset();
    const content = ShareEditorContent(
      projectId: 'photo_first',
      headline: 'SEND ME A PERSONAL DARE',
      secondaryText: 'Think I won’t?',
      ownerName: 'Alex',
      ownerHandle: 'alex',
      avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
      cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
      caption: 'Caption',
      publicLink: 'https://ptw.to/p/photo_first',
    );
    const lookIds = [
      'project_focus',
      'hot_dare',
      'candy_hype',
      'night_detective',
      'yellow_chaos',
    ];
    final values = <ShareEditorValue>[];
    for (final lookId in lookIds) {
      final controller = ShareEditorController(theme: theme, content: content);
      controller.selectLook(lookId);
      values.add(controller.value);
      controller.dispose();
    }

    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          key: const ValueKey('photo_first_looks_golden'),
          color: const Color(0xFF0E1423),
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                for (var index = 0; index < values.length; index++) ...[
                  if (index > 0) const SizedBox(width: 10),
                  SizedBox(
                    width: 180,
                    height: 320,
                    child: GeneratedShareRenderer(
                      theme: theme,
                      content: content,
                      value: values[index],
                      showSelection: false,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(
      find.byKey(const ValueKey('photo_first_looks_golden')),
    );
    await tester.runAsync(
      () => Future.wait([
        for (final path in [
          'assets/images/users/alex.jpg',
          'assets/images/backgrounds/startup.jpg',
          'assets/images/decorations/pixel_cat.png',
          'assets/images/decorations/candy_heart.png',
          'assets/images/decorations/doodle_heart.png',
          'assets/images/decorations/palm_leaf.png',
          'assets/images/decorations/flamingo.png',
          'assets/images/decorations/gesture_figure.png',
          'assets/images/decorations/sparkle.png',
        ])
          precacheImage(AssetImage(path), context),
      ]),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byKey(const ValueKey('photo_first_looks_golden')),
      matchesGoldenFile('../goldens/generated_photo_first_looks.png'),
    );
  });
}
