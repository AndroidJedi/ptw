import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/ui_kit/atoms/ptw_duck_icon.dart';
import 'package:ptw/ui_kit/atoms/ptw_finish_flag_icon.dart';

void main() {
  testWidgets('duck and finish flag keep their compact requested sizes', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Row(
            children: [
              PtwDuckIcon(key: ValueKey('duck')),
              PtwFinishFlagIcon(key: ValueKey('flag'), size: 20),
            ],
          ),
        ),
      ),
    );

    expect(
      tester.getSize(find.byKey(const ValueKey('duck'))),
      const Size.square(18),
    );
    expect(
      tester.getSize(find.byKey(const ValueKey('flag'))),
      const Size.square(20),
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('duck')),
        matching: find.byType(CustomPaint),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('flag')),
        matching: find.byType(CustomPaint),
      ),
      findsOneWidget,
    );
  });
}
