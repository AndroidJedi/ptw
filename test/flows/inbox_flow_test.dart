import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';

import '../test_harness.dart';

void main() {
  testWidgets(
    'inbox shows full responses, reads them, and keeps them private',
    (tester) async {
      final environment = await pumpPtw(tester, initialLocation: '/inbox');
      await tester.pumpAndSettle();

      expect(find.text('Anonymous inbox'), findsNothing);
      expect(find.textContaining('only you can see'), findsNothing);
      expect(
        find.byKey(const ValueKey(ComponentIds.inboxBack)),
        findsOneWidget,
      );
      expect(find.text('THEY BELIEVE'), findsNWidgets(2));
      expect(find.text('THEY DOUBT'), findsOneWidget);
      expect(find.text('1'), findsNothing);
      expect(
        find.text(
          'I would join this. The idea feels useful and genuinely social.',
        ),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('response_seed_response_1')),
        findsOneWidget,
      );

      final panels = find.byKey(const ValueKey('response_seed_response_1'));
      final nextPanels = find.byKey(const ValueKey('response_seed_response_2'));
      expect(
        tester.getTopLeft(panels).dy,
        lessThan(tester.getTopLeft(nextPanels).dy),
      );

      final stored = await environment.repository.load();
      final displayedResponses = stored!.responses.where(
        (item) => item.projectId == 'challenge_red_friday',
      );
      expect(displayedResponses.every((item) => item.isRead), isTrue);
      expect(
        stored.responses
            .where((item) => item.projectId != 'challenge_red_friday')
            .every((item) => !item.isRead),
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
