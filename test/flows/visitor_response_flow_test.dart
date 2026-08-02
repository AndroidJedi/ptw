import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('visitor must choose a side and message, then can send again', (
    tester,
  ) async {
    final environment = await pumpPtw(tester, initialLocation: '/alexbuilds');

    expect(find.text('Community pulse'), findsNothing);
    expect(find.text('THE HONEST STORY'), findsNothing);
    expect(find.byKey(const ValueKey(ComponentIds.visitorBack)), findsNothing);
    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(
      tester
          .widget<PtwBlackButton>(
            find.byKey(const ValueKey(ComponentIds.responseSend)),
          )
          .onPressed,
      isNull,
    );

    await tester.tap(find.byKey(const ValueKey(ComponentIds.responseBelieve)));
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.responseMessage)),
      'You have the momentum. Keep shipping.',
    );
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.responseSend)));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey(ComponentIds.responseSent)),
      findsOneWidget,
    );
    expect((await environment.repository.load())!.responses.length, 6);

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseStartProject)),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.actionSheet)),
      findsOneWidget,
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.responseSendAnother)),
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextField>(
            find.byKey(const ValueKey(ComponentIds.responseMessage)),
          )
          .controller!
          .text,
      isEmpty,
    );
  });
}
