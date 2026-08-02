import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/theme/ptw_colors.dart';
import 'package:ptw/models/ptw_image_ref.dart';

import '../test_harness.dart';

void main() {
  testWidgets('imported device image is persisted as a file reference', (
    tester,
  ) async {
    final media = FakePtwMediaService(
      pickResult: const PtwImageRef.file('ptw_media/imported.jpg'),
    );
    final environment = await pumpPtw(
      tester,
      initialLocation: '/projects/new',
      media: media,
    );
    await tester.enterText(
      find.byKey(const ValueKey(ComponentIds.createProjectGoal)),
      'Use a real image for this project',
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectDeadline)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectContinue)),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectDeviceImage)),
    );
    await tester.pump();
    await tester.tap(
      find.byKey(ValueKey('color_${PtwColors.teal.toARGB32()}')),
    );
    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.createProjectPublish)),
    );
    await tester.pumpAndSettle();

    final stored = await environment.repository.load();
    expect(stored!.projects.first.image.source, PtwImageSource.file);
    expect(stored.projects.first.image.path, 'ptw_media/imported.jpg');
    expect(stored.projects.first.primaryColor, PtwColors.teal.toARGB32());
  });
}
