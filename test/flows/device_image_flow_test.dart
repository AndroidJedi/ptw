import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/ptw_media_service.dart';

import '../test_harness.dart';

void main() {
  testWidgets('cancelling a share photo replacement keeps the project photo', (
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
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyToolPhoto)));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_replace_background')));
    await tester.pumpAndSettle();

    expect(media.pickCount, 1);
    expect(media.lastSharePurpose, PtwShareImagePurpose.background);
    expect(
      (await environment.repository.load())!
          .draft!
          .storyComposition!
          .backgroundId,
      isNull,
    );
  });
}
