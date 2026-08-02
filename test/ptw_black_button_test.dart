import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/theme/ptw_colors.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';
import 'package:ptw/ui_kit/atoms/ptw_sticker_text.dart';

void main() {
  testWidgets('black CTAs use one centered sticker label and no icon', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              PtwBlackButton(
                key: const ValueKey('enabled'),
                label: 'Add proof',
                onPressed: () {},
              ),
              const PtwBlackButton(
                key: ValueKey('disabled'),
                label: 'Continue',
                onPressed: null,
              ),
            ],
          ),
        ),
      ),
    );

    for (final key in const ['enabled', 'disabled']) {
      final button = find.byKey(ValueKey(key));
      expect(
        find.descendant(of: button, matching: find.byType(Text)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: button, matching: find.byType(Icon)),
        findsNothing,
      );
      expect(
        find.descendant(of: button, matching: find.byType(PtwStickerText)),
        findsOneWidget,
      );
    }
    final enabled = tester.widget<Text>(find.text('Add proof'));
    final disabled = tester.widget<Text>(find.text('Continue'));
    expect(enabled.textAlign, TextAlign.center);
    expect(enabled.style!.fontFamily, PtwStickerText.fontFamily);
    expect(enabled.style!.fontSize, 20);
    expect(enabled.style!.color, PtwColors.textOnAccent);
    expect(enabled.style!.shadows, hasLength(9));
    expect(enabled.style!.shadows!.first.color, PtwColors.hotPink);
    expect(enabled.style!.shadows!.first.offset, const Offset(2, 2));
    expect(enabled.style!.shadows![1].color, PtwColors.ink);
    expect(disabled.style!.color!.a, closeTo(0.55, 0.01));
  });
}
