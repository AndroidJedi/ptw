import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_project_draft.dart';

import '../test_harness.dart';

void main() {
  testWidgets('clean installs open a ready minimal Story', (tester) async {
    final environment = await pumpPtw(
      tester,
      initialLocation: '/projects/new',
      activated: false,
    );

    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyBuilderCanvas)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolTemplates)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolText)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolPhoto)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.shareGenerateAnother)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyContinue)),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey(ComponentIds.shareBack)), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectDoubt)),
      findsNothing,
    );
    expect(find.byKey(const ValueKey('project_progress_metric')), findsNothing);
    expect(find.byKey(const ValueKey('confirm_journey')), findsNothing);
    expect(find.byKey(const ValueKey('share_candidate_list')), findsNothing);
    expect(find.text('Template'), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolLooks)),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolEffects)),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.storyToolDecor)),
      findsNothing,
    );
    expect(find.byKey(const ValueKey(ComponentIds.projectHome)), findsNothing);
    final stored = await environment.repository.load();
    expect(stored!.draft!.intent, PtwProjectDraftIntent.firstProject);
    expect(stored.draft!.goal, 'Ship the idea everyone says is too ambitious');
    expect(stored.draft!.image.path, 'assets/images/backgrounds/startup.jpg');
    expect(stored.draft!.storyComposition!.journeyState, 'beginning');
    expect(stored.draft!.storyComposition!.lookId, 'static_note_1');
  });

  testWidgets('Template control switches layout without leaving the editor', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.storyToolTemplates)),
    );
    await tester.pump();
    expect(find.byKey(const ValueKey('story_template_tray')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('story_template_hero_photo')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey('story_template_progress')));
    await tester.pump(const Duration(milliseconds: 400));

    expect(
      find.byKey(const ValueKey(ComponentIds.storyBuilderCanvas)),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('share_candidate_list')), findsNothing);
    final story =
        (await environment.repository.load())!.draft!.storyComposition!;
    expect(story.templateId, 'progress');
    expect(story.familyId, 'progress');
  });

  testWidgets('later challenges ask only for the required goal', (
    tester,
  ) async {
    await pumpPtw(tester, initialLocation: '/projects/new');

    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectDoubt)),
      findsNothing,
    );
    expect(find.byKey(const ValueKey('project_progress_metric')), findsNothing);
    expect(
      find.byKey(const ValueKey('project_category_business')),
      findsNothing,
    );

    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Start one focused new challenge',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey(ComponentIds.storyBuilderCanvas)),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('confirm_journey')), findsNothing);
    expect(find.byKey(const ValueKey('share_candidate_list')), findsNothing);
  });
}
