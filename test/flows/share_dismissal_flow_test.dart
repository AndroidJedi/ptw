import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/features/share/share_service.dart';
import 'package:ptw/models/ptw_share_record.dart';

import '../test_harness.dart';

void main() {
  testWidgets('dismissed native share stays on the final guide step', (
    tester,
  ) async {
    final share = FakePtwShareService(
      result: const PtwShareResult(status: PtwShareResultStatus.dismissed),
    );
    final environment = await pumpPtw(tester, activated: false, share: share);
    await reachSharePreview(tester);
    await openStoryGuideAtFinalStep(tester);
    await submitFinalStoryShare(tester);

    final stored = await environment.repository.load();
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(
      find.text('Share sheet closed. Your Story is still here.'),
      findsOneWidget,
    );
    expect(stored!.draft, isNull);
    expect(stored.activatedAt, isNotNull);
    expect(stored.currentProjectByOwner['user_alex'], isNotNull);
    expect(stored.shareRecords.first.outcome, PtwShareOutcome.dismissed);
    expect(stored.shareRecords[1].outcome, PtwShareOutcome.copied);
  });
}

Future<void> reachSharePreview(WidgetTester tester) async {
  await editStoryHeadline(tester, 'Build something people say cannot work');
}
