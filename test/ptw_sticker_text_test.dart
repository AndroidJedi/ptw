import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/theme/ptw_colors.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/ui_kit/atoms/ptw_sticker_text.dart';
import 'package:ptw/ui_kit/organisms/ptw_project_tile.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    final font = FontLoader(PtwStickerText.fontFamily)
      ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'));
    await font.load();
  });

  testWidgets('sticker variants keep one text node and adaptive colors', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              PtwStickerText.hero('Sent!', key: ValueKey('hero')),
              PtwStickerText.action(
                'Share project',
                key: ValueKey('action'),
                accentColor: PtwColors.electricBlue,
              ),
              PtwStickerText.action(
                'Disabled action',
                key: ValueKey('disabled'),
                enabled: false,
              ),
              PtwStickerText.actionSheet(
                'Primary sheet action',
                key: ValueKey('sheet'),
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.byType(PtwStickerText), findsNWidgets(4));
    expect(find.text('Share project'), findsOneWidget);
    expect(find.bySemanticsLabel('Share project'), findsOneWidget);
    for (final key in const ['hero', 'action', 'disabled', 'sheet']) {
      expect(
        find.descendant(
          of: find.byKey(ValueKey(key)),
          matching: find.byType(Text),
        ),
        findsOneWidget,
      );
    }

    final hero = tester.widget<Text>(
      find.descendant(
        of: find.byKey(const ValueKey('hero')),
        matching: find.byType(Text),
      ),
    );
    final action = tester.widget<Text>(
      find.descendant(
        of: find.byKey(const ValueKey('action')),
        matching: find.byType(Text),
      ),
    );
    final disabled = tester.widget<Text>(
      find.descendant(
        of: find.byKey(const ValueKey('disabled')),
        matching: find.byType(Text),
      ),
    );
    expect(hero.style!.fontFamily, PtwStickerText.fontFamily);
    expect(hero.style!.color, PtwColors.textOnAccent);
    expect(hero.style!.shadows, hasLength(17));
    expect(action.style!.color, PtwColors.electricBlue);
    expect(action.style!.shadows, hasLength(8));
    expect(disabled.style!.color!.a, closeTo(0.55, 0.01));
    semantics.dispose();
  });

  testWidgets('ninety-character goals fit every active project tile height', (
    tester,
  ) async {
    const goal =
        'Launch the boldest community project and welcome one hundred active people before the fina';
    expect(goal.length, 90);
    final project = PtwProject(
      id: 'long_goal',
      ownerId: 'owner',
      ownerName: 'Alex',
      ownerHandle: 'alexbuilds',
      ownerAvatarAsset: 'assets/images/users/alex.jpg',
      goal: goal,
      deadline: DateTime(2026, 12, 31),
      image: const PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
      primaryColor: PtwColors.teal.toARGB32(),
      status: PtwProjectStatus.active,
      createdAt: DateTime(2026, 8, 2),
    );

    for (final configuration in const <({double height, bool compact})>[
      (height: 244, compact: true),
      (height: 280, compact: false),
      (height: 410, compact: false),
    ]) {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 353,
                child: PtwProjectTile(
                  project: project,
                  height: configuration.height,
                  compact: configuration.compact,
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      expect(tester.takeException(), isNull);
      expect(find.text(goal), findsOneWidget);
      expect(
        tester
            .getSize(find.byKey(const ValueKey(ComponentIds.projectTile)))
            .height,
        configuration.height,
      );
      final renderedGoal = tester.widget<Text>(find.text(goal));
      expect(renderedGoal.maxLines, isNull);
      expect(
        renderedGoal.style!.fontSize,
        inInclusiveRange(configuration.compact ? 20 : 22, 38),
      );
    }
  });
}
