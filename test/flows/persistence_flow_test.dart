import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets('created project survives a complete app restart', (
    tester,
  ) async {
    final environment = await pumpPtw(tester);
    final context = tester.element(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
    );
    final state = PtwScope.of(context);
    const goal = 'Persist this project after restart';
    await state.createProject(
      goal: goal,
      deadline: DateTime(2026, 12, 31),
      image: const PtwImageRef.asset('assets/images/backgrounds/creative.jpg'),
      primaryColor: 0xFF7A32FF,
    );
    await tester.pumpAndSettle();

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await pumpPtw(
      tester,
      repository: environment.repository,
      media: environment.media,
    );
    expect(find.text(goal), findsOneWidget);
  });
}
