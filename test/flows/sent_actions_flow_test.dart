import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('sent screen supports back and creator actions', (tester) async {
    await pumpPtw(tester, initialLocation: '/p/challenge_red_friday/sent');

    await tester.tap(find.byKey(const ValueKey(ComponentIds.responseSentBack)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.visitorComposer)),
      findsOneWidget,
    );

    final context = tester.element(
      find.byKey(const ValueKey(ComponentIds.visitorComposer)),
    );
    GoRouter.of(context).go('/p/challenge_red_friday/sent');
    await tester.pumpAndSettle();
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
