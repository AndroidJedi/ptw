import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_response.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets(
    'inbox shows full responses, reads them, and keeps them private',
    (tester) async {
      final seed = await const MockJsonLoader().load();
      final current = seed.snapshot.projects.firstWhere(
        (project) => project.id == 'challenge_red_friday',
      );
      final previousProject = PtwProject(
        id: 'previous_project',
        ownerId: current.ownerId,
        ownerName: current.ownerName,
        ownerHandle: current.ownerHandle,
        ownerAvatarAsset: current.ownerAvatarAsset,
        goal: 'A previous private project',
        deadline: DateTime(2026, 7, 1),
        image: current.image,
        primaryColor: current.primaryColor,
        status: PtwProjectStatus.completed,
        createdAt: DateTime(2026, 5, 1),
      );
      final previousResponse = PtwResponse(
        id: 'previous_response',
        projectId: previousProject.id,
        side: PtwResponseSide.doubt,
        message: 'This belongs to the previous project.',
        createdAt: DateTime(2026, 7, 1),
      );
      final repository = MemoryPrototypeRepository(
        initial: seed.snapshot.copyWith(
          projects: [previousProject, ...seed.snapshot.projects],
          responses: [previousResponse, ...seed.snapshot.responses],
        ),
      );
      final environment = await pumpPtw(
        tester,
        initialLocation: '/inbox',
        repository: repository,
      );
      await tester.pumpAndSettle();

      expect(find.text('Anonymous inbox'), findsNothing);
      expect(find.textContaining('only you can see'), findsNothing);
      expect(
        find.byKey(const ValueKey(ComponentIds.inboxBack)),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey(ComponentIds.inboxShare)),
        findsOneWidget,
      );
      expect(find.byType(PtwBlackButton), findsOneWidget);
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
      expect(find.text('This belongs to the previous project.'), findsNothing);

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

      await tester.tap(find.byKey(const ValueKey(ComponentIds.inboxShare)));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey(ComponentIds.shareScreen)),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('share_template_criticism')),
        findsOneWidget,
      );
      expect(find.byType(PtwBlackButton), findsOneWidget);

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
