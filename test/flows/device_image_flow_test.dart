import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('device picker cancellation leaves image explicitly unselected', (
    tester,
  ) async {
    final media = FakePtwMediaService();
    await pumpPtw(tester, initialLocation: '/projects/new', media: media);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'A project that needs a real photo',
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
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectDeviceImage)),
    );
    await tester.pumpAndSettle();
    expect(media.pickCount, 1);
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectPublish)),
    );
    await tester.pump();
    expect(find.text('Choose a project image and color.'), findsOneWidget);
  });
}
