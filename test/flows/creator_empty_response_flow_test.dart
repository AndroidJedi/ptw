import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';

import '../test_harness.dart';

void main() {
  testWidgets('empty current project is backfilled without hiding reactions', (
    tester,
  ) async {
    final seed = await const MockJsonLoader().load();
    final repository = MemoryPrototypeRepository(
      initial: seed.snapshot.copyWith(
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
    await pumpPtw(tester, repository: repository);
    await tester.pumpAndSettle();

    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(
      find.byKey(const ValueKey(ComponentIds.projectAddProof)),
      findsOneWidget,
    );
    await tester.dragUntilVisible(
      find.byKey(const ValueKey(ComponentIds.projectOpenReactions)),
      find.byType(ListView),
      const Offset(0, -250),
    );
    expect(find.text('The first milestone is complete'), findsOneWidget);
    expect(find.text('The next step is scheduled'), findsOneWidget);
    expect(
      find.text(
        'This feels specific enough to follow. Keep showing the progress.',
      ),
      findsOneWidget,
    );
    expect(find.text('All reactions · 3 unread'), findsOneWidget);

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
    await tester.dragUntilVisible(
      find.byKey(
        const ValueKey('response_demo_response_challenge_red_friday_5'),
      ),
      find.byType(ListView),
      const Offset(0, -250),
    );
    expect(
      find.byKey(
        const ValueKey('response_demo_response_challenge_red_friday_5'),
      ),
      findsOneWidget,
    );
  });
}
