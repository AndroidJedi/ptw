import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('Story editor only offers project and bundled backgrounds', (
    tester,
  ) async {
    final media = FakePtwMediaService();
    final environment = await pumpPtw(
      tester,
      initialLocation: '/projects/new',
      media: media,
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'A project that can add a real photo later',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyToolLooks)));
    await tester.pump();
    await tester.ensureVisible(
      find.byKey(const ValueKey('story_background_technology')),
    );
    await tester.tap(find.byKey(const ValueKey('story_background_technology')));
    await tester.pumpAndSettle();

    expect(media.pickCount, 0);
    expect(
      (await environment.repository.load())!
          .draft!
          .storyComposition!
          .backgroundId,
      'technology',
    );
  });
}
