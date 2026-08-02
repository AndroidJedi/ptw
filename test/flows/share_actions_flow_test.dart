import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('share outcomes live behind one pinned action', (tester) async {
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
      initialLocation: '/projects/challenge_red_friday/share',
    );

    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(find.text('PTW.TO/ALEXBUILDS'), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareCopyLink)),
      findsNothing,
    );

    await tester.tap(find.byKey(const ValueKey(ComponentIds.sharePrimary)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.actionSheet)),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.shareCopyLink)));
    await tester.pumpAndSettle();
    expect(copiedText, 'https://ptw.to/alexbuilds');

    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey(ComponentIds.sharePrimary)));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.shareActionStories)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Project card prepared for Stories'), findsOneWidget);
  });
}
