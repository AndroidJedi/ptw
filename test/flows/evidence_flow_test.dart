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
    expect(find.byKey(const ValueKey('confirm_journey')), findsOneWidget);
    final smallWin = tester.widget<ChoiceChip>(
      find.byKey(const ValueKey('journey_smallWin')),
    );
    expect(smallWin.selected, isTrue);
    await tester.tap(find.byKey(const ValueKey('confirm_journey')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('share_candidate_list')), findsOneWidget);
    final list = tester.widget<ListView>(
      find.byKey(const ValueKey('share_candidate_list')),
    );
    expect(list.childrenDelegate.estimatedChildCount, 5);
    final stored = await environment.repository.load();
    expect(stored!.evidence.first.title, 'Interviewed 20 potential users');
  });
}
