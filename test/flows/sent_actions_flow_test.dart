import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('sent screen exposes both outcomes through one CTA', (
    tester,
  ) async {
    await pumpPtw(tester, initialLocation: '/p/challenge_red_friday/sent');

    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.responseSendAnother)),
      findsNothing,
    );

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseStartProject)),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseSendAnother)),
    );
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
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseActionStartProject)),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectScreen)),
      findsOneWidget,
    );
  });
}
