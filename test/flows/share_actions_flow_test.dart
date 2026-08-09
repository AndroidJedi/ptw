import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_share_generation_event.dart';

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
    await openStoryBuilder(tester);
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
    await tester.tap(find.byKey(const ValueKey('story_editor_done')));
    await tester.pumpAndSettle();
    expect(find.text('Watch me prove this.'), findsWidgets);

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.shareGenerateAnother)),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('share_candidate_list')), findsOneWidget);
    expect(find.text('Use this'), findsAtLeastNWidgets(1));
    await tester.tap(find.text('Use this').first);
    await tester.pumpAndSettle();

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
    final events =
        stored.shareGenerationEvents
            .where((item) => item.projectId == 'challenge_red_friday')
            .toList()
            .reversed
            .toList();
    expect(
      events.map((item) => item.type),
      containsAllInOrder([
        ShareGenerationEventType.generationStarted,
        ShareGenerationEventType.stateConfirmed,
        ShareGenerationEventType.candidatesShown,
        ShareGenerationEventType.optionsRegenerated,
        ShareGenerationEventType.exportCompleted,
        ShareGenerationEventType.shareInvoked,
      ]),
    );
    expect(events.every((event) => event.elapsedMilliseconds != null), isTrue);
    for (var index = 1; index < events.length; index++) {
      expect(
        events[index].elapsedMilliseconds!,
        greaterThanOrEqualTo(events[index - 1].elapsedMilliseconds!),
      );
    }
    const allowedEventKeys = {
      'id',
      'sessionId',
      'projectId',
      'type',
      'timestamp',
      'candidateId',
      'journeyState',
      'elapsedMilliseconds',
    };
    expect(
      events.every(
        (event) => event.toJson().keys.every(allowedEventKeys.contains),
      ),
      isTrue,
      reason: 'instrumentation must never store user copy or media',
    );
  });
}
