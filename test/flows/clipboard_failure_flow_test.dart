import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_share_record.dart';

import '../test_harness.dart';

void main() {
  testWidgets('clipboard failure preserves the draft and records the attempt', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, activated: false);
    await editStoryHeadline(tester, 'Build something people say cannot work');
    var clipboardCalls = 0;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          clipboardCalls++;
          throw PlatformException(code: 'clipboard_denied');
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

    await openStoryShareStep(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final stored = await environment.repository.load();
    expect(clipboardCalls, 1);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    expect(stored!.draft, isNotNull);
    expect(stored.activatedAt, isNull);
    expect(
      stored.projects.where((project) => project.id == stored.draft!.id),
      isEmpty,
    );
    expect(stored.shareRecords.first.outcome, PtwShareOutcome.failed);
    expect(stored.shareRecords.first.target, 'clipboard');
    expect(stored.shareRecords, hasLength(1));
    expect(stored.shareRecords.single.story, isNotNull);
  });
}
