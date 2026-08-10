import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/ptw_media_service.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets('ready Story headline autosaves and restores into fresh state', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await editStoryHeadline(tester, 'Resume this unfinished challenge');
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
    expect(restoredState.draft!.doubt, 'Think I won’t?');
    expect(
      restoredState.draft!.storyComposition!.headline,
      'Resume this unfinished challenge',
    );
    restoredState.dispose();
  });

  testWidgets('Story edits autosave and reopen in the constructor', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await editStoryHeadline(
      tester,
      'Make this challenge impossible to scroll past',
    );
    await openStoryBuilder(tester);
    environment.media.pickResult = const PtwImageRef.file(
      'ptw_media/share_draft_photo.webp',
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyToolPhoto)));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_replace_background')));
    await tester.pumpAndSettle();
    expect(environment.media.lastSharePurpose, PtwShareImagePurpose.background);
    await tester.tap(find.byKey(const ValueKey('story_canvas_headline')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const ValueKey('story_headline_field')),
      'This headline exists only in my Story',
    );
    await tester.tap(find.byKey(const ValueKey('story_editor_done')));
    await tester.pump(const Duration(milliseconds: 400));

    final saved = await environment.repository.load();
    expect(
      saved!.draft!.storyComposition!.headline,
      'This headline exists only in my Story',
    );
    expect(saved.draft!.goal, 'This headline exists only in my Story');
    expect(saved.draft!.storyComposition!.dare, isNotEmpty);
    expect(saved.draft!.image.path, 'assets/images/backgrounds/startup.jpg');
    expect(
      (((saved.draft!.storyComposition!.editorValue!['backgroundEdit']
              as Map)['image']
          as Map)['path']),
      'ptw_media/share_draft_photo.webp',
    );

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await pumpPtw(
      tester,
      activated: false,
      repository: environment.repository,
      media: environment.media,
      share: environment.share,
    );
    expect(find.text('This headline exists only in my Story'), findsWidgets);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.storyToolPhoto)));
    await tester.pump();
    final projectPhoto = tester.widget<FilterChip>(
      find.byKey(const ValueKey('story_use_project_photo')),
    );
    expect(projectPhoto.selected, isFalse);
  });
}
