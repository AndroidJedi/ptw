import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets('returning launch share layer closes to the current project', (
    tester,
  ) async {
    await pumpPtw(tester);
    expect(
      find.byKey(const ValueKey(ComponentIds.shareScreen)),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey('journey_close')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );
  });
}
