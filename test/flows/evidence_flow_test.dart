import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('creator publishes proof and it is persisted on project home', (
    tester,
  ) async {
    final environment = await pumpPtw(tester);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectShare)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectAddProof)));
    await tester.pumpAndSettle();
    expect(find.byType(PtwBlackButton), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.evidenceTitle)),
      'Interviewed 20 potential users',
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.evidenceDetails)),
      'The strongest need is now clear.',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.addEvidencePublish)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Interviewed 20 potential users'), findsOneWidget);
    final stored = await environment.repository.load();
    expect(stored!.evidence.first.title, 'Interviewed 20 potential users');
  });
}
