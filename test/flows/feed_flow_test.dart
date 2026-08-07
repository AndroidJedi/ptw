import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';
import 'package:ptw/ui_kit/organisms/ptw_project_tile.dart';

import '../test_harness.dart';

void main() {
  testWidgets('combined image feed opens projects and returns naturally', (
    tester,
  ) async {
    await pumpPtw(tester, initialLocation: '/feed');

    expect(find.byKey(const ValueKey(ComponentIds.feedScreen)), findsOneWidget);
    expect(find.byKey(const ValueKey(ComponentIds.feedBack)), findsOneWidget);
    expect(find.byType(PtwBlackButton), findsNothing);
    expect(find.byType(PtwProjectTile), findsNothing);
    expect(
      find.byKey(const ValueKey('activity_proof_evidence_003')),
      findsOneWidget,
    );
    expect(find.text('Three kilograms down this week'), findsOneWidget);
    expect(
      find.text('The first 14 sign-ups arrived in two days'),
      findsNothing,
    );
    expect(find.textContaining('@alexbuilds'), findsNothing);

    await tester.tap(find.byKey(const ValueKey('activity_proof_evidence_003')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.visitorComposer)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.visitorBack)),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey(ComponentIds.visitorBack)));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey(ComponentIds.feedScreen)), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey(ComponentIds.feedBack)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
  });
}
