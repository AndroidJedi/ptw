import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project_draft.dart';
import 'package:ptw/state/ptw_app_state.dart';

import '../test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'clean state bootstraps a ready first-project draft from the theme',
    () async {
      final repository = MemoryPrototypeRepository();
      final state = PtwAppState(
        repository: repository,
        mediaService: FakePtwMediaService(),
        shareService: FakePtwShareService(),
        now: () => testNow,
      );

      await state.load();

      expect(state.draft!.intent, PtwProjectDraftIntent.firstProject);
      expect(state.draft!.goal, 'Ship the idea everyone says is too ambitious');
      expect(state.draft!.doubt, 'Think I won’t?');
      expect(state.draft!.hasPreview, isTrue);
      expect(state.draft!.category, isNotNull);
      expect(
        state.draft!.image,
        const PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
      );
      state.dispose();
    },
  );

  test('load preserves an existing meaningful draft exactly', () async {
    final seed = await const MockJsonLoader().load();
    final existing = PtwProjectDraft(
      id: 'keep_this_draft',
      intent: PtwProjectDraftIntent.firstProject,
      goal: 'Keep my real unfinished goal',
      doubt: 'Keep my real doubt',
      image: const PtwImageRef.asset('assets/images/backgrounds/fitness.jpg'),
      primaryColor: 0xFF123456,
      createdAt: testNow.subtract(const Duration(days: 2)),
      updatedAt: testNow.subtract(const Duration(days: 1)),
    );
    final repository = MemoryPrototypeRepository(
      initial: seed.snapshot.copyWith(draft: existing),
    );
    final state = PtwAppState(
      repository: repository,
      mediaService: FakePtwMediaService(),
      shareService: FakePtwShareService(),
      now: () => testNow,
    );

    await state.load();

    expect(state.draft!.toJson(), existing.toJson());
    state.dispose();
  });
}
