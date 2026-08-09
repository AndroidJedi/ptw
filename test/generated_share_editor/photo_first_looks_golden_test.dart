import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late ShareThemeConfig theme;

  setUpAll(() async {
    theme = await ShareThemeBundle.loadAsset();
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

  testWidgets('all 18 numbered looks render as six series of three', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1150, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
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
    final values = <ShareEditorValue>[];
    for (final look in theme.looks) {
      final controller = ShareEditorController(theme: theme, content: content);
      controller.selectLook(look.id);
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
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final value in values)
                  SizedBox(
                    width: 180,
                    height: 320,
                    child: GeneratedShareRenderer(
                      theme: theme,
                      content: content,
                      value: value,
                      showSelection: false,
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
      find.byKey(const ValueKey('photo_first_looks_golden')),
    );
    final usedStickerIds =
        values
            .expand((value) => value.stickers)
            .map((item) => item.stickerId)
            .toSet();
    await tester.runAsync(
      () => Future.wait([
        for (final path in {
          'assets/images/users/alex.jpg',
          'assets/images/backgrounds/startup.jpg',
          ...theme.stickers
              .where((sticker) => usedStickerIds.contains(sticker.id))
              .map((sticker) => theme.asset(sticker.assetId).path)
              .whereType<String>(),
        })
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
