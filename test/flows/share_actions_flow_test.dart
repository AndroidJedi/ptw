import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('Story constructor edits, cycles, resets, and shares', (
    tester,
  ) async {
    final environment = await pumpPtw(
      tester,
      initialLocation:
          '/projects/challenge_red_friday/share?event=challengeCreated',
    );

    expect(find.text('BUILD YOUR STORY'), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.sharePlatformSelector)),
      findsNothing,
    );

    await tester.tap(find.byKey(const ValueKey('story_canvas_headline')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const ValueKey('story_headline_field')),
      'Watch me prove this.',
    );
    await tester.enterText(
      find.byKey(const ValueKey('story_dare_field')),
      'Say I can’t.',
    );
    await tester.tap(find.byKey(const ValueKey('story_editor_done')));
    await tester.pumpAndSettle();
    expect(find.text('Watch me prove this.'), findsWidgets);
    expect(find.text('Say I can’t.'), findsWidgets);

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.shareGenerateAnother)),
    );
    await tester.pump();
    expect(find.text('Watch me prove this.'), findsWidgets);
    expect(find.byKey(const ValueKey('story_reset')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('story_reset')));
    await tester.pump();
    expect(find.text('Watch me prove this.'), findsNothing);

    await openStoryGuideAtFinalStep(tester);
    await submitFinalStoryShare(tester);

    expect(environment.share.shareCount, 1);
    expect(
      environment.share.lastText,
      contains('https://ptw.to/p/challenge_red_friday'),
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );
    final stored = await environment.repository.load();
    expect(stored!.shareRecords.first.projectId, 'challenge_red_friday');
    expect(stored.shareRecords.first.story, isNotNull);
    expect(stored.shareRecords.first.format.name, 'story');
  });
}
