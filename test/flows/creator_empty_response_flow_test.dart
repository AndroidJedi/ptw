import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';

import '../test_harness.dart';

void main() {
  testWidgets('empty current project stays empty and prioritizes sharing', (
    tester,
  ) async {
    final seed = await const MockJsonLoader().load();
    final repository = MemoryPrototypeRepository(
      initial: seed.snapshot.copyWith(
        currentProjectByOwner: {
          ...seed.snapshot.currentProjectByOwner,
          seed.currentUser.id: seed.currentUser.initialProjectId,
        },
        activatedAt: testNow.subtract(const Duration(days: 35)),
        responses: [
          for (final response in seed.snapshot.responses)
            if (response.projectId != 'challenge_red_friday') response,
        ],
        evidence: [
          for (final proof in seed.snapshot.evidence)
            if (proof.projectId != 'challenge_red_friday') proof,
        ],
      ),
    );
    await pumpPtw(
      tester,
      repository: repository,
      initialLocation: '/projects/challenge_red_friday',
    );
    await tester.pumpAndSettle();

    expect(find.text('Your challenge is live.'), findsOneWidget);
    expect(
      find.text('Reactions and comments will appear here.'),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.projectShareAgain)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.projectAddProof)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.projectAudiencePulse)),
      findsNothing,
    );
    expect(find.text('The first milestone is complete'), findsNothing);
    expect(
      (await repository.load())!.responses.where(
        (item) => item.projectId == 'challenge_red_friday',
      ),
      isEmpty,
    );
  });
}
