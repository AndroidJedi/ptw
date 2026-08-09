import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('builder edits text directly and keeps it across share back', (
    tester,
  ) async {
    await pumpPtw(
      tester,
      initialLocation:
          '/projects/challenge_red_friday/share?event=challengeCreated',
    );
    await openStoryBuilder(tester);

    expect(find.byKey(const ValueKey('story_template_tray')), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyBuilderCanvas)),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey('story_canvas_headline')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.storyHeadlineField)),
      '   ',
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyContinue)));
    await tester.pump();
    expect(
      find.text('Add a short headline before continuing.'),
      findsOneWidget,
    );
    expect(find.text('READY TO SHARE'), findsNothing);

    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.storyHeadlineField)),
      'Watch this challenge happen.',
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyEditorDone)));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyContinue)));
    await tester.pumpAndSettle();

    expect(find.text('READY TO SHARE'), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareCopyLink)),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareBack)));
    await tester.pumpAndSettle();
    expect(find.text('Watch this challenge happen.'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('candidate selection persists generated metadata', (
    tester,
  ) async {
    final environment = await pumpPtw(
      tester,
      initialLocation:
          '/projects/challenge_red_friday/share?event=challengeCreated',
    );

    await openStoryBuilder(tester);
    expect(find.byKey(const ValueKey('story_template_tray')), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolStickers)),
      findsNothing,
    );

    await openStoryShareStep(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump(const Duration(milliseconds: 500));

    final stored = await environment.repository.load();
    final story = stored!.shareRecords.first.story!;
    expect(
      story.editorValue!['templateId'],
      isIn([
        'hero_photo',
        'progress',
        'comparison',
        'documentary',
        'conflict',
        'milestone_number',
        'proof_card',
      ]),
    );
    expect(story.candidateId, isNotNull);
    expect(story.familyId, isNotNull);
  });
}
