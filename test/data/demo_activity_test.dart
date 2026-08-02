import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets(
    'demo activity backfills once and is committed with new projects',
    (tester) async {
      final seed = await const MockJsonLoader().load();
      final repository = _RecordingRepository(
        seed.snapshot.copyWith(
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
      final state = PtwAppState(
        repository: repository,
        mediaService: FakePtwMediaService(),
        now: () => testNow,
      );

      await state.load();
      expect(state.responsesFor('challenge_red_friday'), hasLength(5));
      expect(state.evidenceFor('challenge_red_friday'), hasLength(2));
      expect(repository.saveCount, 1);
      final responseIds =
          state
              .responsesFor('challenge_red_friday')
              .map((item) => item.id)
              .toSet();
      final proofIds =
          state
              .evidenceFor('challenge_red_friday')
              .map((item) => item.id)
              .toSet();

      await state.load();
      expect(state.responsesFor('challenge_red_friday'), hasLength(5));
      expect(state.evidenceFor('challenge_red_friday'), hasLength(2));
      expect(
        state
            .responsesFor('challenge_red_friday')
            .map((item) => item.id)
            .toSet(),
        responseIds,
      );
      expect(
        state
            .evidenceFor('challenge_red_friday')
            .map((item) => item.id)
            .toSet(),
        proofIds,
      );
      expect(repository.saveCount, 1);

      final project = await state.createProject(
        goal: 'Test every creator flow',
        deadline: DateTime(2026, 12, 31),
        image: const PtwImageRef.asset(
          'assets/images/backgrounds/creative.jpg',
        ),
        primaryColor: 0xFF7A32FF,
      );

      expect(repository.saveCount, 2);
      final stored = (await repository.load())!;
      expect(stored.currentProjectByOwner['user_alex'], project.id);
      final responses = stored.responses.where(
        (item) => item.projectId == project.id,
      );
      final evidence = stored.evidence.where(
        (item) => item.projectId == project.id,
      );
      expect(responses, hasLength(5));
      expect(responses.every((item) => !item.isRead), isTrue);
      expect(evidence, hasLength(2));
      expect(evidence.where((item) => item.media != null), hasLength(1));

      state.dispose();
    },
  );
}

final class _RecordingRepository implements PtwPrototypeRepository {
  _RecordingRepository(this.snapshot);

  PtwPrototypeSnapshot? snapshot;
  int saveCount = 0;

  @override
  Future<PtwPrototypeSnapshot?> load() async => snapshot;

  @override
  Future<void> reset() async => snapshot = null;

  @override
  Future<void> save(PtwPrototypeSnapshot snapshot) async {
    saveCount++;
    this.snapshot = PtwPrototypeSnapshot.fromJson(snapshot.toJson());
  }
}
