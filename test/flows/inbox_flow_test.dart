import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../test_harness.dart';

void main() {
  testWidgets(
    'opening an anonymous response marks it read and keeps it private',
    (tester) async {
      final environment = await pumpPtw(tester, initialLocation: '/inbox');
      expect(find.text('1 unread · only you can see these'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('response_seed_response_3')));
      await tester.pumpAndSettle();
      expect(find.text('THEY BELIEVE'), findsOneWidget);
      final stored = await environment.repository.load();
      expect(
        stored!.responses
            .firstWhere((item) => item.id == 'seed_response_3')
            .isRead,
        isTrue,
      );

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      await pumpPtw(
        tester,
        initialLocation: '/alexbuilds',
        repository: environment.repository,
        media: environment.media,
      );
      expect(
        find.text(
          'I would join this. The idea feels useful and genuinely social.',
        ),
        findsNothing,
      );
    },
  );
}
