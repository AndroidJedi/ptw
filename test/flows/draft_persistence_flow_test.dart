import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets('draft autosaves and restores into a fresh app state', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Resume this unfinished challenge',
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectDoubt)),
      'The deadline is intimidating.',
    );
    await tester.pump(const Duration(milliseconds: 350));
    expect(
      (await environment.repository.load())!.draft!.goal,
      'Resume this unfinished challenge',
    );

    final restoredState = PtwAppState(
      repository: environment.repository,
      mediaService: environment.media,
      shareService: environment.share,
      now: () => testNow,
    );
    await restoredState.load();
    expect(restoredState.draft!.goal, 'Resume this unfinished challenge');
    expect(restoredState.draft!.doubt, 'The deadline is intimidating.');
    restoredState.dispose();
  });

  testWidgets('Story edits autosave and reopen in the constructor', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Make this challenge impossible to scroll past',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('story_canvas_headline')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const ValueKey('story_headline_field')),
      'This headline exists only in my Story',
    );
    await tester.enterText(
      find.byKey(const ValueKey('story_dare_field')),
      'Would you bet against me?',
    );
    await tester.tap(find.byKey(const ValueKey('story_editor_done')));
    await tester.pump(const Duration(milliseconds: 400));

    final saved = await environment.repository.load();
    expect(
      saved!.draft!.storyComposition!.headline,
      'This headline exists only in my Story',
    );
    expect(saved.draft!.storyComposition!.dare, 'Would you bet against me?');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await pumpPtw(
      tester,
      activated: false,
      repository: environment.repository,
      media: environment.media,
      share: environment.share,
    );
    expect(find.text('This headline exists only in my Story'), findsOneWidget);
    expect(find.text('Would you bet against me?'), findsOneWidget);
  });
}
