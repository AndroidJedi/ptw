import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_reaction_summary.dart';
import 'package:ptw/ui_kit/organisms/ptw_audience_pulse.dart';

void main() {
  testWidgets('audience pulse exposes counts and a proportional split', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 353,
            child: PtwAudiencePulse(
              summary: PtwReactionSummary(believe: 3, doubt: 2),
            ),
          ),
        ),
      ),
    );

    expect(find.text('5 reactions'), findsNothing);
    expect(find.text('3 BELIEVE'), findsOneWidget);
    expect(find.text('2 DOUBT'), findsOneWidget);
    expect(find.bySemanticsLabel('3 believe, 2 doubt'), findsOneWidget);
    final fill = tester.widget<FractionallySizedBox>(
      find.descendant(
        of: find.byKey(const ValueKey(ComponentIds.projectAudienceMeter)),
        matching: find.byType(FractionallySizedBox),
      ),
    );
    expect(fill.widthFactor, 0.6);
    semantics.dispose();
  });

  testWidgets('audience pulse hides when there are no reactions', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: PtwAudiencePulse(
          summary: PtwReactionSummary(believe: 0, doubt: 0),
        ),
      ),
    );

    expect(find.text('0 reactions'), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.projectAudienceMeter)),
      findsNothing,
    );
  });
}
