import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_image_ref.dart';

import '../test_harness.dart';

void main() {
  testWidgets('Story background edit does not mutate the project photo', (
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
      'Use a real image for this project',
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

    await openStoryShareStep(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump(const Duration(milliseconds: 500));

    final stored = await environment.repository.load();
    final created = stored!.projects.first;
    expect(created.image, isA<PtwImageRef>());
    expect(created.image.source, PtwImageSource.asset);
    expect(created.image.path, 'assets/images/backgrounds/startup.jpg');
    expect(stored.shareRecords.first.story!.backgroundId, 'technology');
  });
}
