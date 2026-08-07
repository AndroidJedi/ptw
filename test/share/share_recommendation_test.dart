import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets('launch recommendations map the newest unshared moment', (
    tester,
  ) async {
    final seed = await const MockJsonLoader().load();
    final activated = seed.snapshot.copyWith(
      currentProjectByOwner: {
        ...seed.snapshot.currentProjectByOwner,
        seed.currentUser.id: seed.currentUser.initialProjectId,
      },
      activatedAt: testNow.subtract(const Duration(days: 35)),
    );
    final milestoneState = PtwAppState(
      repository: MemoryPrototypeRepository(initial: activated),
      mediaService: FakePtwMediaService(),
      shareService: FakePtwShareService(),
      now: () => testNow,
    );
    await milestoneState.load();

    final milestone = milestoneState.recommendedShareFor(
      'challenge_red_friday',
    );
    expect(milestone.event, ShareEvent.milestoneReached);
    expect(milestone.template, ShareTemplateType.milestone);
    expect(milestone.momentId, 'proof:evidence_001');
    milestoneState.dispose();

    final doubt = seed.snapshot.responses.firstWhere(
      (item) =>
          item.projectId == 'challenge_red_friday' && item.side.name == 'doubt',
    );
    final doubtState = PtwAppState(
      repository: MemoryPrototypeRepository(
        initial: activated.copyWith(
          responses: [doubt],
          evidence: [
            for (final item in seed.snapshot.evidence)
              if (item.projectId != 'challenge_red_friday') item,
          ],
        ),
      ),
      mediaService: FakePtwMediaService(),
      shareService: FakePtwShareService(),
      now: () => testNow,
    );
    await doubtState.load();

    final criticism = doubtState.recommendedShareFor('challenge_red_friday');
    expect(criticism.event, ShareEvent.newSkeptic);
    expect(criticism.template, ShareTemplateType.criticism);
    expect(criticism.momentId, 'response:${doubt.id}');
    doubtState.dispose();
  });
}
