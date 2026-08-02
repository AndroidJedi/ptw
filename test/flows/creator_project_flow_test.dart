import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_response.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';
import 'package:ptw/ui_kit/organisms/ptw_project_tile.dart';

import '../test_harness.dart';

void main() {
  testWidgets(
    'creator project shows recent proofs and reactions with permanent routes',
    (tester) async {
      final seed = await const MockJsonLoader().load();
      final allUnread = [
        for (final response in seed.snapshot.responses)
          PtwResponse(
            id: response.id,
            projectId: response.projectId,
            side: response.side,
            message: response.message,
            createdAt: response.createdAt,
          ),
      ];
      final repository = MemoryPrototypeRepository(
        initial: seed.snapshot.copyWith(responses: allUnread),
      );
      await pumpPtw(tester, repository: repository);
      await tester.pumpAndSettle();

      final hero = find.byKey(const ValueKey(ComponentIds.projectHero));
      expect(hero, findsOneWidget);
      expect(tester.getTopLeft(hero).dx, 0);
      expect(tester.getSize(hero).width, testSurfaceSize.width);
      expect(find.byType(PtwProjectTile), findsNothing);
      expect(find.byType(PtwBlackButton), findsOneWidget);
      expect(
        find.byKey(const ValueKey(ComponentIds.projectAddProof)),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey(ComponentIds.projectOpenFeed)),
        findsOneWidget,
      );
      expect(find.text('Open feed'), findsNothing);

      await tester.tap(
        find.byKey(const ValueKey(ComponentIds.projectOpenFeed)),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey(ComponentIds.feedScreen)),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const ValueKey(ComponentIds.feedBack)));
      await tester.pumpAndSettle();

      await tester.dragUntilVisible(
        find.text('The landing page is live'),
        find.byType(ListView),
        const Offset(0, -250),
      );
      expect(find.text('The landing page is live'), findsOneWidget);
      expect(
        find.text(
          'I published the first version and connected a working waitlist form.',
        ),
        findsOneWidget,
      );
      expect(
        find.text('The first 14 sign-ups arrived in two days'),
        findsOneWidget,
      );
      expect(
        find.text(
          'People are registering, which means the direction is worth pursuing.',
        ),
        findsOneWidget,
      );

      await tester.dragUntilVisible(
        find.byKey(const ValueKey(ComponentIds.projectOpenReactions)),
        find.byType(ListView),
        const Offset(0, -250),
      );
      expect(
        find.byKey(const ValueKey('home_response_seed_response_1')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('home_response_seed_response_2')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('home_response_seed_response_3')),
        findsNothing,
      );
      expect(find.text('All reactions · 1 unread'), findsOneWidget);

      final storedAfterPreview = await repository.load();
      final currentResponses = storedAfterPreview!.responses.where(
        (response) => response.projectId == 'challenge_red_friday',
      );
      expect(
        currentResponses
            .where((response) => response.id != 'seed_response_3')
            .every((response) => response.isRead),
        isTrue,
      );
      expect(
        currentResponses
            .singleWhere((response) => response.id == 'seed_response_3')
            .isRead,
        isFalse,
      );

      await tester.ensureVisible(
        find.byKey(const ValueKey(ComponentIds.projectOpenReactions)),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const ValueKey(ComponentIds.projectOpenReactions)),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey(ComponentIds.inboxScreen)),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('response_seed_response_3')),
        findsOneWidget,
      );
      final storedAfterInbox = await repository.load();
      expect(
        storedAfterInbox!.responses
            .where((response) => response.projectId == 'challenge_red_friday')
            .every((response) => response.isRead),
        isTrue,
      );
    },
  );
}
