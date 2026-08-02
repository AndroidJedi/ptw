import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('sent screen can start a new creator project', (tester) async {
    await pumpPtw(tester, initialLocation: '/p/challenge_red_friday/sent');
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseStartProject)),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectScreen)),
      findsOneWidget,
    );
  });
}
