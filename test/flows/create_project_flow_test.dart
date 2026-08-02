import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/theme/ptw_colors.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';
import 'package:ptw/ui_kit/atoms/ptw_finish_flag_icon.dart';

import '../test_harness.dart';

void main() {
  testWidgets('creator chooses every required field and lands on share', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, initialLocation: '/projects/new');
    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(find.byType(PtwFinishFlagIcon), findsOneWidget);
    const goal = 'Ship the boldest local launch of the year';
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      goal,
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

    await tester.tap(find.byKey(const ValueKey('curated_startup')));
    await tester.tap(
      find.byKey(ValueKey('color_${PtwColors.hotPink.toARGB32()}')),
    );
    await tester.pump();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectPublish)),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(find.text(goal), findsOneWidget);
    final stored = await environment.repository.load();
    expect(stored!.projects.first.goal, goal);
    expect(stored.currentProjectByOwner['user_alex'], stored.projects.first.id);
    final projectId = stored.projects.first.id;
    expect(
      stored.responses.where((item) => item.projectId == projectId),
      hasLength(5),
    );
    expect(
      stored.evidence.where((item) => item.projectId == projectId),
      hasLength(2),
    );
    final project = stored.projects.first;
    final proof = stored.evidence.firstWhere(
      (item) => item.projectId == projectId && item.media != null,
    );
    expect(proof.media!.path, isNot(project.image.path));
  });
}
