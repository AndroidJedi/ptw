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

    expect(
      find.byKey(const ValueKey(ComponentIds.storyStickerTray)),
      findsOneWidget,
    );
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
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.storyDareField)),
      ' ',
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyContinue)));
    await tester.pump();
    expect(find.text('Both Story lines are required.'), findsOneWidget);
    expect(find.text('READY TO SHARE'), findsNothing);

    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.storyHeadlineField)),
      'Watch this challenge happen.',
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.storyDareField)),
      'Try to stop me.',
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
    expect(find.text('BUILD YOUR STORY'), findsOneWidget);
    expect(find.text('Watch this challenge happen.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('sticker tray adds, transforms, selects, and deletes layers', (
    tester,
  ) async {
    final environment = await pumpPtw(
      tester,
      initialLocation:
          '/projects/challenge_red_friday/share?event=challengeCreated',
    );

    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyToolLooks)));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_look_project_focus')));
    await tester.pump();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.storyToolStickers)),
    );
    await tester.pump();

    await tester.tap(find.byKey(const ValueKey('story_sticker_cheering_blob')));
    await tester.pump();
    expect(
      find.byKey(const ValueKey(ComponentIds.storyTransformHandle)),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('story_delete_sticker')), findsOneWidget);
    await tester.drag(
      find.byKey(const ValueKey(ComponentIds.storyTransformHandle)),
      const Offset(18, -12),
    );
    await tester.pump();

    await tester.tap(find.byKey(const ValueKey('story_sticker_victory_hand')));
    await tester.tap(find.byKey(const ValueKey('story_sticker_turbo_rocket')));
    await tester.pump();
    expect(find.text('3/3 · Delete one to add'), findsOneWidget);

    await tester.tap(
      find.byKey(const ValueKey('story_canvas_sticker_cheering_blob_1')),
    );
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_delete_sticker')));
    await tester.pump();
    expect(find.text('2/3'), findsOneWidget);

    await openStoryShareStep(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump(const Duration(milliseconds: 500));

    final stored = await environment.repository.load();
    final story = stored!.shareRecords.first.story!;
    expect(story.stickers, hasLength(2));
    expect(
      story.stickers.any((item) => item.stickerId == 'cheering_blob'),
      isFalse,
    );
    expect(
      story.stickers.any((item) => item.stickerId == 'turbo_rocket'),
      isTrue,
    );
  });
}
