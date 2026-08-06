import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('share hub edits, varies, copies, and opens guided handoff', (
    tester,
  ) async {
    String? copiedText;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copiedText =
              (call.arguments as Map<Object?, Object?>)['text'] as String?;
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );

    await pumpPtw(
      tester,
      initialLocation:
          '/projects/challenge_red_friday/share?event=challengeCreated',
    );

    expect(find.text('Get Your First Doubts'), findsOneWidget);
    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareTemplateSelector)),
      findsOneWidget,
    );
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey(ComponentIds.sharePlatformSelector)),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.sharePlatformSelector)),
      findsOneWidget,
    );

    final copyLink = find.byKey(const ValueKey(ComponentIds.shareCopyLink));
    await tester.ensureVisible(copyLink);
    await tester.tap(copyLink);
    await tester.pump();
    expect(copiedText, 'https://ptw.to/p/challenge_red_friday');

    final edit = find.byKey(const ValueKey(ComponentIds.shareEditText));
    await tester.tap(edit);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.shareEditHook)),
      'Watch me answer this.',
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.shareEditCaption)),
      'The public version of my promise.',
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareEditSave)));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey(ComponentIds.sharePreview)),
      -300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Watch me answer this.'), findsOneWidget);

    final another = find.byKey(
      const ValueKey(ComponentIds.shareGenerateAnother),
    );
    await tester.scrollUntilVisible(
      another,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(another);
    await tester.pump();
    expect(find.text('Watch me answer this.'), findsNothing);

    tester
        .widget<PtwBlackButton>(
          find.byKey(const ValueKey(ComponentIds.sharePrimary)),
        )
        .onPressed!();
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 300)),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.storyShareGuide)),
      findsOneWidget,
    );

    for (var step = 0; step < 3; step++) {
      final next = find.byKey(const ValueKey(ComponentIds.storyShareGuideNext));
      await tester.ensureVisible(next);
      await tester.tap(next);
      await tester.pumpAndSettle();
    }
    final finish = find.byKey(
      const ValueKey(ComponentIds.storyShareGuideFinish),
    );
    await tester.ensureVisible(finish);
    await tester.tap(finish);
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.storyViewer)),
      findsOneWidget,
    );
    expect(find.text('Your card is ready'), findsOneWidget);
  });
}
