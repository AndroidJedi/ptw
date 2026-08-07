import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/features/share/share_service.dart';
import 'package:ptw/models/ptw_share_record.dart';

import '../test_harness.dart';

void main() {
  testWidgets('unconfirmed share exposes copy fallback that activates', (
    tester,
  ) async {
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (_) async => null,
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    final share = FakePtwShareService(
      result: const PtwShareResult(status: PtwShareResultStatus.unavailable),
    );
    final environment = await pumpPtw(tester, activated: false, share: share);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Build something people say cannot work',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();
    await openStoryGuideAtFinalStep(tester);
    await submitFinalStoryShare(tester);
    expect(
      find.text('Sharing could not be confirmed. Retry or copy the link.'),
      findsOneWidget,
    );
    expect(find.text('Copy link'), findsOneWidget);

    final stored = await environment.repository.load();
    expect(
      find.byKey(const ValueKey('instagram_guide_next_4')),
      findsOneWidget,
    );
    expect(stored!.draft, isNull);
    expect(stored.activatedAt, isNotNull);
    expect(stored.shareRecords.first.outcome, PtwShareOutcome.unavailable);
    expect(stored.shareRecords[1].outcome, PtwShareOutcome.copied);
  });
}
