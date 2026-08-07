import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_project_draft.dart';

import '../test_harness.dart';

void main() {
  testWidgets('clean installs cannot enter the new-challenge route', (
    tester,
  ) async {
    final environment = await pumpPtw(
      tester,
      initialLocation: '/projects/new',
      activated: false,
    );

    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey(ComponentIds.projectHome)), findsNothing);
    final stored = await environment.repository.load();
    expect(stored!.draft!.intent, PtwProjectDraftIntent.firstProject);
  });
}
