import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('generated editor can be disposed and opened again', (
    tester,
  ) async {
    const route = '/projects/challenge_red_friday/share?event=challengeCreated';
    await pumpPtw(tester, initialLocation: route);
    await openStoryBuilder(tester);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyContinue)),
      findsOneWidget,
    );

    await pumpPtw(tester, initialLocation: route);
    await openStoryBuilder(tester);
    expect(tester.takeException(), isNull);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyContinue)),
      findsOneWidget,
    );
  });

  testWidgets('generated editor is available in a following test case', (
    tester,
  ) async {
    const route = '/projects/challenge_red_friday/share?event=challengeCreated';
    await pumpPtw(tester, initialLocation: route);
    expect(tester.takeException(), isNull);
    expect(find.text('READY TO SHARE'), findsNothing);
    expect(
      find.text('This Story is no longer available.'),
      findsNothing,
      reason: 'the seeded project should still resolve',
    );
    expect(find.text('Local data unavailable'), findsNothing);
    expect(find.byKey(const ValueKey('confirm_journey')), findsOneWidget);
  });
}
