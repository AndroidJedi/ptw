import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('creator publishes proof and lands on milestone sharing', (
    tester,
  ) async {
    final environment = await pumpPtw(
      tester,
      initialLocation: '/projects/challenge_red_friday/proof/new',
    );
    expect(find.byType(PtwBlackButton), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.evidenceTitle)),
      'Interviewed 20 potential users',
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.evidenceDetails)),
      'The strongest need is now clear.',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.addEvidencePublish)),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyContinue)),
      findsOneWidget,
    );
    final stored = await environment.repository.load();
    expect(stored!.evidence.first.title, 'Interviewed 20 potential users');
    expect(stored.shareGenerationEvents.first.journeyState, 'smallWin');
  });
}
