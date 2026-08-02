import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('create project visual step golden', (tester) async {
    await pumpPtw(tester, initialLocation: '/projects/new');
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Launch my project and reach 100 active people',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectDeadline)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.pump();
    await expectLater(
      find.byType(PtwApp),
      matchesGoldenFile('../../goldens/v2_create_project.png'),
    );
  });
}
