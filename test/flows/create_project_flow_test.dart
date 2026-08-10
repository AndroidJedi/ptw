import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('first native share activates the saved draft exactly once', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyContinue)),
      findsOneWidget,
    );
    const goal = 'Ship the boldest local launch of the year';
    await editStoryHeadline(tester, goal);

    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    await openStoryBuilder(tester);
    expect(find.text(goal), findsWidgets);
    final beforeShare = await environment.repository.load();
    expect(beforeShare!.draft!.goal, goal);
    expect(beforeShare.projects.where((item) => item.goal == goal), isEmpty);

    await openStoryGuideAtFinalStep(tester);
    final afterCopy = await environment.repository.load();
    expect(afterCopy!.draft, isNull);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    await submitFinalStoryShare(tester);

    expect(environment.share.shareCount, 1);
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );
    expect(find.text('Your challenge is live.'), findsOneWidget);
    final stored = await environment.repository.load();
    final project = stored!.projects.firstWhere((item) => item.goal == goal);
    expect(project.doubt, 'Think I won’t?');
    expect(stored.currentProjectByOwner['user_alex'], project.id);
    expect(stored.draft, isNull);
    expect(stored.shareRecords, hasLength(2));
    expect(
      stored.shareRecords.every((item) => item.projectId == project.id),
      isTrue,
    );
    expect(stored.shareRecords.first.story, isNotNull);
    expect(
      stored.responses.where((item) => item.projectId == project.id),
      isEmpty,
    );
    expect(
      stored.evidence.where((item) => item.projectId == project.id),
      isEmpty,
    );
  });

  testWidgets('Copy activates once and leaves the constructor open', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await editStoryHeadline(
      tester,
      'Turn one copied link into a real challenge',
    );
    await openStoryShareStep(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump(const Duration(milliseconds: 500));

    var stored = await environment.repository.load();
    final projectId = stored!.currentProjectByOwner['user_alex'];
    expect(projectId, isNotNull);
    expect(stored.projects.where((item) => item.id == projectId), hasLength(1));
    expect(stored.draft, isNull);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(find.text('Copied'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump(const Duration(milliseconds: 500));
    stored = await environment.repository.load();
    expect(
      stored!.projects.where((item) => item.id == projectId),
      hasLength(1),
    );
    expect(stored.shareRecords, hasLength(2));
  });
}
