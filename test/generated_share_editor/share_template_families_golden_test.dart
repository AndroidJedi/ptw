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

  testWidgets('all seven framework families keep fixed authored layouts', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1170, 630));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    const content = ShareEditorContent(
      projectId: 'families',
      headline: 'THE NEXT VERSION IS REAL',
      secondaryText: 'They said the plan was too ambitious.',
      ownerName: 'Alex',
      ownerHandle: 'alex',
      avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
      cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
      previousMedia: ShareImageValue.asset(
        'assets/images/backgrounds/business.jpg',
      ),
      currentMedia: ShareImageValue.asset(
        'assets/images/backgrounds/startup.jpg',
      ),
      progressValue: '50%',
      metricValue: '50 USERS',
      previousTimeLabel: 'BEFORE',
      currentTimeLabel: 'NOW',
      proofLabel: 'WAITLIST IS LIVE',
      caption: 'A factual project update',
      publicLink: 'https://ptw.to/p/families',
    );
    const lookIds = [
      'soft_focus_1',
      'pixel_pop_1',
      'static_note_1',
      'holo_crush_1',
      'peach_collage_1',
      'legacy_victory_1',
      'soft_focus_2',
    ];
    final values = <ShareEditorValue>[];
    for (var index = 0; index < theme.templates.length; index++) {
      final controller = ShareEditorController(theme: theme, content: content);
      controller.selectTemplate(theme.templates[index].id);
      controller.selectLook(lookIds[index]);
      values.add(controller.value.copyWith(stickers: const []));
      controller.dispose();
    }

    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          key: const ValueKey('share_template_families_golden'),
          color: const Color(0xFF0E1423),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final value in values)
                  SizedBox(
                    width: 155,
                    height: 276,
                    child: GeneratedShareRenderer(
                      theme: theme,
                      content: content,
                      value: value,
                      showSelection: false,
                      interactionEnabled: false,
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
      find.byKey(const ValueKey('share_template_families_golden')),
    );
    await tester.runAsync(
      () => Future.wait([
        for (final path in const {
          'assets/images/users/alex.jpg',
          'assets/images/backgrounds/startup.jpg',
          'assets/images/backgrounds/business.jpg',
        })
          precacheImage(AssetImage(path), context),
      ]),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byKey(const ValueKey('share_template_families_golden')),
      matchesGoldenFile('../goldens/generated_share_template_families.png'),
    );
  });
}
