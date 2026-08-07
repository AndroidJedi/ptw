import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_project_draft.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';
import 'package:ptw/models/ptw_response.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  testWidgets('newly activated projects remain genuinely empty', (
    tester,
  ) async {
    final seed = await const MockJsonLoader().load();
    final repository = _RecordingRepository(seed.snapshot);
    final state = PtwAppState(
      repository: repository,
      mediaService: FakePtwMediaService(),
      shareService: FakePtwShareService(),
      now: () => testNow,
    );

    await state.load();
    final project = await activateTestDraft(
      state,
      goal: 'Test every creator flow',
      intent: PtwProjectDraftIntent.firstProject,
      deadline: DateTime(2026, 12, 31),
    );

    expect(state.responsesFor(project.id), isEmpty);
    expect(state.evidenceFor(project.id), isEmpty);
    await state.load();
    expect(state.responsesFor(project.id), isEmpty);
    expect(state.evidenceFor(project.id), isEmpty);

    await state.submitResponse(
      projectId: project.id,
      side: PtwResponseSide.doubt,
      message: 'One real doubt for the live summary.',
    );
    final summary = state.reactionSummaryFor(project.id);
    expect(summary.total, 1);
    expect(summary.doubt, 1);
    expect(repository.saveCount, greaterThanOrEqualTo(1));

    state.dispose();
  });
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
