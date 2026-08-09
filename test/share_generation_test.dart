import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_generation.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/features/story/ptw_generated_story_adapter.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';
import 'package:ptw/models/ptw_evidence.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_share_record.dart';
import 'package:ptw/models/ptw_story_composition.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('project generation metadata', () {
    test('category inference requires a unique highest keyword score', () {
      const suggester = PtwProjectCategorySuggester();
      expect(
        suggester.suggest('Code an AI software tool'),
        PtwProjectCategory.technology,
      );
      expect(
        suggester.suggest('Run a marathon and improve fitness'),
        PtwProjectCategory.fitness,
      );
      expect(
        suggester.suggest('Build an app and run'),
        PtwProjectCategory.other,
      );
    });

    test('progress metrics clamp and round-trip with projects', () {
      const metric = PtwProgressMetric(
        start: 10,
        current: 55,
        target: 100,
        unit: 'users',
      );
      expect(metric.fraction, 0.5);
      expect(metric.percentage, 50);
      final project = _project(progressMetric: metric);
      final decoded = PtwProject.fromJson(project.toJson());
      expect(decoded.progressMetric?.toJson(), metric.toJson());
      expect(decoded.categoryConfirmed, isTrue);
    });

    test('legacy journey values migrate to the canonical eight states', () {
      final base = _story().toJson();
      expect(
        PtwStoryComposition.fromJson({
          ...base,
          'journeyState': 'grind',
        }).journeyState,
        ShareJourneyState.grinding.name,
      );
      expect(
        PtwStoryComposition.fromJson({
          ...base,
          'journeyState': 'result',
        }).journeyState,
        ShareJourneyState.finish.name,
      );
      expect(
        PtwStoryComposition.fromJson({
          ...base,
          'journeyState': 'setback',
        }).journeyState,
        ShareJourneyState.failure.name,
      );
    });
  });

  group('journey recommendation', () {
    const recommender = PtwJourneyRecommender();

    test('uses the required recommendation priority', () {
      expect(
        recommender.recommend(
          project: _project(),
          evidence: const [],
          shares: const [],
        ),
        ShareJourneyState.beginning,
      );
      expect(
        recommender.recommend(
          project: _project(status: PtwProjectStatus.completed),
          evidence: const [],
          shares: const [],
        ),
        ShareJourneyState.finish,
      );
      expect(
        recommender.recommend(
          project: _project(
            progressMetric: const PtwProgressMetric(
              start: 0,
              current: 50,
              target: 100,
              unit: 'users',
            ),
          ),
          evidence: const [],
          shares: const [],
        ),
        ShareJourneyState.milestone,
      );
      expect(
        recommender.recommend(
          project: _project(),
          evidence: [_evidence('new', createdAt: _now)],
          shares: const [],
        ),
        ShareJourneyState.smallWin,
      );
    });

    test('recovery follows a confirmed failure and new proof', () {
      final failedAt = _now.subtract(const Duration(days: 1));
      final previous = PtwShareRecord(
        id: 'share_failure',
        projectId: 'project_1',
        source: PtwShareSource.project,
        outcome: PtwShareOutcome.success,
        story: _story(
          journeyState: ShareJourneyState.failure.name,
          createdAt: failedAt,
        ),
        format: ShareFormat.story,
        startedAt: failedAt,
        completedAt: failedAt,
      );
      expect(
        recommender.recommend(
          project: _project(),
          evidence: [_evidence('after', createdAt: _now)],
          shares: [previous],
        ),
        ShareJourneyState.recovery,
      );
    });
  });

  group('candidate generation', () {
    test('all eight journey states have three no-proof fallbacks', () async {
      final theme = await ShareThemeBundle.loadAsset();
      const generator = PtwShareCandidateGenerator();
      final journeys = ShareJourneyState.values.where(
        (state) => state != ShareJourneyState.unassigned,
      );
      for (final journey in journeys) {
        final candidates = generator.generate(
          ShareGenerationContext(
            theme: theme,
            project: _project(doubt: null),
            evidence: const [],
            responses: const [],
            previousShares: const [],
            event: ShareEvent.manual,
            journeyState: journey,
            now: _now,
          ),
        );
        expect(candidates, hasLength(3), reason: journey.name);
      }
    });

    test(
      'is deterministic and always returns three varied candidates',
      () async {
        final theme = await ShareThemeBundle.loadAsset();
        final context = ShareGenerationContext(
          theme: theme,
          project: _project(doubt: 'Nobody thinks it will work'),
          evidence: [
            _evidence('latest', media: const PtwImageRef.asset('latest.png')),
            _evidence('older', media: const PtwImageRef.asset('older.png')),
          ],
          responses: const [],
          previousShares: const [],
          event: ShareEvent.manual,
          journeyState: ShareJourneyState.grinding,
          now: _now,
          stickersAllowed: true,
        );
        const generator = PtwShareCandidateGenerator();
        final first = generator.generate(context);
        final second = generator.generate(context);

        expect(first, hasLength(3));
        expect(first.map((item) => item.id), second.map((item) => item.id));
        expect(first.map((item) => item.family).toSet(), hasLength(3));
        expect(
          first
              .map((item) => item.lookId.replaceFirst(RegExp(r'_[123]$'), ''))
              .toSet(),
          hasLength(3),
        );
        expect(first.every((item) => item.stickersAllowed), isTrue);
      },
    );

    test('new options use a new stable trio', () async {
      final theme = await ShareThemeBundle.loadAsset();
      ShareGenerationContext context(int index) => ShareGenerationContext(
        theme: theme,
        project: _project(),
        evidence: const [],
        responses: const [],
        previousShares: const [],
        event: ShareEvent.manual,
        journeyState: ShareJourneyState.beginning,
        now: _now,
        regenerationIndex: index,
      );
      const generator = PtwShareCandidateGenerator();
      final first = generator.generate(context(0));
      final regenerated = generator.generate(context(1));
      expect(
        first.map((item) => item.id).toSet(),
        isNot(regenerated.map((item) => item.id).toSet()),
      );
      expect(regenerated, hasLength(3));
    });

    test(
      'recommendation event participates in ranking and stable IDs',
      () async {
        final theme = await ShareThemeBundle.loadAsset();
        ShareGenerationContext context(ShareEvent event) =>
            ShareGenerationContext(
              theme: theme,
              project: _project(
                progressMetric: const PtwProgressMetric(
                  start: 0,
                  current: 50,
                  target: 100,
                  unit: 'users',
                ),
              ),
              evidence: [_evidence('real')],
              responses: const [],
              previousShares: const [],
              event: event,
              journeyState: ShareJourneyState.milestone,
              now: _now,
            );
        const generator = PtwShareCandidateGenerator();
        final manual = generator.generate(context(ShareEvent.manual));
        final milestone = generator.generate(
          context(ShareEvent.milestoneReached),
        );

        expect(milestone.first.family, ShareTemplateFamily.milestone);
        expect(
          milestone.map((item) => item.id).toSet(),
          isNot(manual.map((item) => item.id).toSet()),
        );
      },
    );

    test('data-dependent families never use invented proof or media', () async {
      final theme = await ShareThemeBundle.loadAsset();
      const generator = PtwShareCandidateGenerator();
      final candidates = generator.generate(
        ShareGenerationContext(
          theme: theme,
          project: _project(doubt: null),
          evidence: const [],
          responses: const [],
          previousShares: const [],
          event: ShareEvent.manual,
          journeyState: ShareJourneyState.beginning,
          now: _now,
        ),
      );
      expect(candidates, hasLength(3));
      expect(
        candidates.map((item) => item.family),
        isNot(contains(ShareTemplateFamily.proof)),
      );
      expect(
        candidates.map((item) => item.family),
        isNot(contains(ShareTemplateFamily.comparison)),
      );
      expect(candidates.every((item) => item.previousMedia == null), isTrue);
    });

    test('comparison media are always distinct', () async {
      final theme = await ShareThemeBundle.loadAsset();
      final context = ShareGenerationContext(
        theme: theme,
        project: _project(),
        evidence: [
          _evidence('latest', media: const PtwImageRef.asset('latest.png')),
          _evidence('older', media: const PtwImageRef.asset('older.png')),
        ],
        responses: const [],
        previousShares: const [],
        event: ShareEvent.manual,
        journeyState: ShareJourneyState.grinding,
        now: _now,
      );
      expect(context.previousMedia?.path, isNot(context.currentMedia.path));
    });

    test(
      'comparison media include the real photo saved in a prior share',
      () async {
        final theme = await ShareThemeBundle.loadAsset();
        final priorValue = ShareEditorValue(
          lookId: theme.defaultLookId,
          templateId: theme.defaultTemplateId,
          backgroundId: 'project_cover',
          layerValues: const {'headline': 'Prior headline'},
          transforms: const {},
          stickers: const [],
          backgroundEdit: const ShareBackgroundEdit(
            image: ShareImageValue.file('/tmp/prior-share.jpg'),
          ),
        );
        final priorStory = _story().copyWith(editorValue: priorValue.toJson());
        final priorShare = PtwShareRecord(
          id: 'share_prior',
          projectId: 'project_1',
          source: PtwShareSource.project,
          outcome: PtwShareOutcome.success,
          story: priorStory,
          format: ShareFormat.story,
          startedAt: _now.subtract(const Duration(days: 1)),
          completedAt: _now.subtract(const Duration(days: 1)),
        );
        final context = ShareGenerationContext(
          theme: theme,
          project: _project(),
          evidence: const [],
          responses: const [],
          previousShares: [priorShare],
          event: ShareEvent.manual,
          journeyState: ShareJourneyState.grinding,
          now: _now,
        );

        expect(context.previousMedia?.path, '/tmp/prior-share.jpg');
        expect(context.previousMedia?.path, isNot(context.currentMedia.path));
      },
    );

    test('uncertain face safety removes semantic stickers', () async {
      final theme = await ShareThemeBundle.loadAsset();
      final project = _project();
      ShareCandidate candidate(bool stickersAllowed) =>
          const PtwShareCandidateGenerator()
              .generate(
                ShareGenerationContext(
                  theme: theme,
                  project: project,
                  evidence: const [],
                  responses: const [],
                  previousShares: const [],
                  event: ShareEvent.manual,
                  journeyState: ShareJourneyState.beginning,
                  now: _now,
                  stickersAllowed: stickersAllowed,
                ),
              )
              .first;
      const adapter = PtwGeneratedStoryAdapter();

      ShareEditorValue value(bool stickersAllowed) {
        final selected = candidate(stickersAllowed);
        final base = adapter.createBase(
          project: project,
          event: ShareEvent.manual,
          now: _now,
          candidate: selected,
        );
        final content = adapter.content(
          project: project,
          composition: base,
          candidate: selected,
        );
        return adapter.value(
          theme: theme,
          content: content,
          composition: base,
          project: project,
          candidate: selected,
        );
      }

      expect(value(false).stickers, isEmpty);
      final safe = value(true).stickers;
      expect(safe, hasLength(3));
      expect(
        safe.every((item) => item.stickerId.startsWith('category_startup_')),
        isTrue,
      );
      expect(
        safe.every((item) {
          final config = theme.sticker(item.stickerId);
          return !config.canMove &&
              !config.canResize &&
              !config.canRotate &&
              !config.canDelete;
        }),
        isTrue,
      );
    });

    test(
      'obsolete templates preserve the saved headline and photo crop',
      () async {
        final theme = await ShareThemeBundle.loadAsset();
        const adapter = PtwGeneratedStoryAdapter();
        final saved = ShareEditorValue(
          lookId: 'soft_focus_1',
          templateId: 'removed_template',
          backgroundId: 'project_cover',
          layerValues: const {'headline': 'My exact edited headline'},
          transforms: const {},
          stickers: const [],
          backgroundEdit: const ShareBackgroundEdit(
            image: ShareImageValue.file('/tmp/replaced-photo.jpg'),
            alignmentX: 0.42,
            alignmentY: -0.31,
            zoom: 1.8,
          ),
        );
        final composition = _story().copyWith(editorValue: saved.toJson());
        final content = adapter.content(
          project: _project(),
          composition: composition,
        );
        final migrated = adapter.value(
          theme: theme,
          content: content,
          composition: composition,
          project: _project(),
        );

        expect(migrated.templateId, theme.defaultTemplateId);
        expect(migrated.layerValues['headline'], 'My exact edited headline');
        expect(migrated.backgroundEdit.image?.path, '/tmp/replaced-photo.jpg');
        expect(migrated.backgroundEdit.alignmentX, 0.42);
        expect(migrated.backgroundEdit.alignmentY, -0.31);
        expect(migrated.backgroundEdit.zoom, 1.8);
      },
    );
  });
}

final _now = DateTime(2026, 8, 9, 12);

PtwProject _project({
  String? doubt = 'They said it was too ambitious',
  PtwProjectStatus status = PtwProjectStatus.active,
  PtwProgressMetric? progressMetric,
}) => PtwProject(
  id: 'project_1',
  ownerId: 'owner_1',
  ownerName: 'Alex',
  ownerHandle: 'alex',
  ownerAvatarAsset: 'avatar.png',
  goal: 'Launch my product',
  doubt: doubt,
  image: const PtwImageRef.asset('cover.png'),
  primaryColor: 0xFF000000,
  status: status,
  createdAt: _now.subtract(const Duration(days: 3)),
  category: PtwProjectCategory.startup,
  categoryConfirmed: true,
  progressMetric: progressMetric,
);

PtwEvidence _evidence(String id, {DateTime? createdAt, PtwImageRef? media}) =>
    PtwEvidence(
      id: id,
      projectId: 'project_1',
      title: 'Real proof $id',
      details: 'A factual update',
      createdAt: createdAt ?? _now,
      media: media,
    );

PtwStoryComposition _story({String? journeyState, DateTime? createdAt}) {
  final timestamp = createdAt ?? _now;
  return PtwStoryComposition(
    projectId: 'project_1',
    eventName: 'manual',
    headline: 'Launch my product',
    dare: 'They said no',
    avatar: const PtwImageRef.asset('avatar.png'),
    projectBackground: const PtwImageRef.asset('cover.png'),
    lookId: 'soft_focus_1',
    textTreatment: PtwStoryTextTreatment.clean,
    caption: 'Launch my product',
    createdAt: timestamp,
    updatedAt: timestamp,
    stickers: const [],
    journeyState: journeyState,
  );
}
