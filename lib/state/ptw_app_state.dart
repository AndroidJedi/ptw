import 'package:flutter/widgets.dart';

import '../core/data/mock_json_loader.dart';
import '../core/data/ptw_media_service.dart';
import '../core/data/ptw_prototype_repository.dart';
import '../features/share/share_models.dart';
import '../features/share/share_generation.dart';
import '../features/share/share_service.dart';
import '../features/social_post_studio/studio_models.dart';
import '../generated_share_editor/generated_share_editor.dart';
import '../models/ptw_evidence.dart';
import '../models/ptw_image_ref.dart';
import '../models/ptw_post_background.dart';
import '../models/ptw_project.dart';
import '../models/ptw_project_draft.dart';
import '../models/ptw_prototype_snapshot.dart';
import '../models/ptw_reaction_summary.dart';
import '../models/ptw_response.dart';
import '../models/ptw_share_record.dart';
import '../models/ptw_share_generation_event.dart';
import '../models/ptw_social_activity.dart';
import '../models/ptw_story_composition.dart';
import '../models/ptw_user.dart';

/// App state backed by a single versioned local prototype snapshot.
final class PtwAppState extends ChangeNotifier
    implements ShareGenerationEventSink {
  static final _seedActivityTime = DateTime(2026, 8, 2, 12);

  PtwAppState({
    MockJsonLoader loader = const MockJsonLoader(),
    PtwPrototypeRepository? repository,
    PtwMediaService? mediaService,
    PtwShareService? shareService,
    DateTime Function()? now,
  }) : _loader = loader,
       repository = repository ?? SharedPreferencesPrototypeRepository(),
       mediaService = mediaService ?? LocalPtwMediaService(),
       shareService = shareService ?? const NativePtwShareService(),
       _now = now ?? DateTime.now;

  final MockJsonLoader _loader;
  final DateTime Function() _now;
  final PtwPrototypeRepository repository;
  final PtwMediaService mediaService;
  final PtwShareService shareService;

  bool isReady = false;
  String? errorMessage;
  late PtwUser currentUser;
  List<PtwPostBackground> curatedImages = [];
  late MemeStickerCatalog stickerCatalog;
  late ShareThemeConfig shareEditorTheme;
  PtwImageRef? recoveredProjectImage;
  late PtwPrototypeSnapshot _snapshot;
  bool _isDisposed = false;

  List<PtwProject> get projects => List.unmodifiable(_snapshot.projects);
  List<PtwResponse> get responses => List.unmodifiable(_snapshot.responses);
  List<PtwEvidence> get evidence => List.unmodifiable(_snapshot.evidence);
  List<PtwShareRecord> get shareRecords =>
      List.unmodifiable(_snapshot.shareRecords);
  List<ShareGenerationEvent> get shareGenerationEvents =>
      List.unmodifiable(_snapshot.shareGenerationEvents);
  PtwProjectDraft? get draft => _snapshot.draft;
  DateTime get now => _now();
  bool get isActivated =>
      _snapshot.activatedAt != null && currentProjectOrNull != null;
  DateTime? get activatedAt => _snapshot.activatedAt;

  Future<void> load() async {
    isReady = false;
    errorMessage = null;
    try {
      final seed = await _loader.load();
      shareEditorTheme = await ShareThemeBundle.loadAsset();
      currentUser = seed.currentUser;
      curatedImages = seed.curatedImages;
      stickerCatalog = seed.stickerCatalog;
      await mediaService.initialize();
      final restored = await repository.load();
      final initial = restored ?? seed.snapshot;
      final withChronologicalActivity = _withChronologicalPrototypeActivity(
        initial,
      );
      _snapshot = _withDistinctPrototypeProofMedia(withChronologicalActivity);
      await repository.save(_snapshot);
      recoveredProjectImage = await mediaService.recoverLostProjectImage();
      isReady = true;
    } catch (error) {
      errorMessage = error.toString();
    }
    if (!_isDisposed) notifyListeners();
  }

  Future<void> reset() async {
    await repository.reset();
    final seed = await _loader.load();
    shareEditorTheme = await ShareThemeBundle.loadAsset();
    currentUser = seed.currentUser;
    curatedImages = seed.curatedImages;
    stickerCatalog = seed.stickerCatalog;
    _snapshot = _withDistinctPrototypeProofMedia(
      _withChronologicalPrototypeActivity(seed.snapshot),
    );
    await repository.save(_snapshot);
    recoveredProjectImage = null;
    errorMessage = null;
    isReady = true;
    if (!_isDisposed) notifyListeners();
  }

  PtwProject get currentProject {
    final project = currentProjectOrNull;
    if (project == null) throw StateError('Creator has no active project');
    return project;
  }

  PtwProject? get currentProjectOrNull {
    final id = _snapshot.currentProjectByOwner[currentUser.id];
    return id == null ? null : maybeProjectById(id);
  }

  PtwProject projectById(String id) =>
      _snapshot.projects.firstWhere((project) => project.id == id);

  PtwProject? maybeProjectById(String id) {
    for (final project in _snapshot.projects) {
      if (project.id == id) return project;
    }
    return null;
  }

  PtwProject? projectForHandle(String handle) {
    final owned = _snapshot.projects.where(
      (project) => project.ownerHandle == handle,
    );
    if (owned.isEmpty) return null;
    final ownerId = owned.first.ownerId;
    final currentId = _snapshot.currentProjectByOwner[ownerId];
    return maybeProjectById(currentId ?? '') ?? owned.first;
  }

  List<PtwResponse> responsesFor(String projectId) {
    final items =
        _snapshot.responses
            .where((response) => response.projectId == projectId)
            .toList();
    items.sort((a, b) {
      final byTime = b.createdAt.compareTo(a.createdAt);
      return byTime == 0 ? a.id.compareTo(b.id) : byTime;
    });
    return items;
  }

  int responseCountFor(String projectId) => responsesFor(projectId).length;

  int unreadResponseCountFor(String projectId) =>
      responsesFor(projectId).where((response) => !response.isRead).length;

  PtwReactionSummary reactionSummaryFor(String projectId) {
    var believe = 0;
    var doubt = 0;
    for (final response in _snapshot.responses) {
      if (response.projectId != projectId) continue;
      switch (response.side) {
        case PtwResponseSide.believe:
          believe++;
          break;
        case PtwResponseSide.doubt:
          doubt++;
          break;
      }
    }
    return PtwReactionSummary(believe: believe, doubt: doubt);
  }

  List<PtwSocialActivity> get socialActivity {
    final projectsById = {
      for (final project in _snapshot.projects) project.id: project,
    };
    final items = <PtwSocialActivity>[];
    for (final project in _snapshot.projects) {
      if (project.ownerId == currentUser.id) continue;
      items.add(PtwSocialActivity.projectStarted(project: project));
    }
    for (final proof in _snapshot.evidence) {
      final project = projectsById[proof.projectId];
      if (project == null || project.ownerId == currentUser.id) continue;
      items.add(PtwSocialActivity.proofAdded(project: project, proof: proof));
    }
    items.sort((a, b) {
      final byTime = b.createdAt.compareTo(a.createdAt);
      return byTime == 0 ? a.id.compareTo(b.id) : byTime;
    });
    return List.unmodifiable(items);
  }

  List<PtwEvidence> evidenceFor(String projectId) {
    final items =
        _snapshot.evidence
            .where((item) => item.projectId == projectId)
            .toList();
    items.sort((a, b) {
      final byTime = b.createdAt.compareTo(a.createdAt);
      return byTime == 0 ? a.id.compareTo(b.id) : byTime;
    });
    return items;
  }

  List<PtwShareRecord> shareRecordsFor(String projectId) {
    final items =
        _snapshot.shareRecords
            .where((item) => item.projectId == projectId)
            .toList();
    items.sort((a, b) => b.completedAt.compareTo(a.completedAt));
    return items;
  }

  Future<PtwProjectDraft> ensureDraft(PtwProjectDraftIntent intent) async {
    final existing = _snapshot.draft;
    if (existing != null && existing.intent == intent) return existing;
    final timestamp = _now();
    final draft = PtwProjectDraft(
      id: 'project_${timestamp.microsecondsSinceEpoch}',
      intent: intent,
      goal: '',
      image: const PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
      primaryColor: 0xFFF4066E,
      createdAt: timestamp,
      updatedAt: timestamp,
    );
    await _commit(_snapshot.copyWith(draft: draft));
    return draft;
  }

  Future<PtwProjectDraft> saveDraft({
    required String goal,
    required String doubt,
    required DateTime? deadline,
    required PtwImageRef image,
    required int primaryColor,
    bool markPreviewGenerated = false,
    PtwProjectCategory? category,
    bool? categoryConfirmed,
    PtwProgressMetric? progressMetric,
    bool clearProgressMetric = false,
  }) async {
    final existing = _snapshot.draft;
    if (existing == null) throw StateError('No project draft exists');
    final timestamp = _now();
    final trimmedDoubt = doubt.trim();
    final next = PtwProjectDraft(
      id: existing.id,
      intent: existing.intent,
      goal: goal.trim(),
      doubt: trimmedDoubt.isEmpty ? null : trimmedDoubt,
      deadline:
          deadline == null
              ? null
              : DateTime(deadline.year, deadline.month, deadline.day),
      image: image,
      primaryColor: primaryColor,
      createdAt: existing.createdAt,
      updatedAt: timestamp,
      previewGeneratedAt:
          markPreviewGenerated ? timestamp : existing.previewGeneratedAt,
      storyComposition: existing.storyComposition,
      category: category ?? existing.category,
      categoryConfirmed: categoryConfirmed ?? existing.categoryConfirmed,
      progressMetric:
          clearProgressMetric
              ? null
              : progressMetric ?? existing.progressMetric,
    );
    await _commit(_snapshot.copyWith(draft: next));
    return next;
  }

  Future<void> saveDraftStory(PtwStoryComposition composition) async {
    final existing = _snapshot.draft;
    if (existing == null || existing.id != composition.projectId) return;
    await _commit(
      _snapshot.copyWith(
        draft: existing.copyWith(
          storyComposition: composition,
          updatedAt: _now(),
        ),
      ),
    );
  }

  Future<PtwProject?> completeStoryShare({
    required PtwStoryComposition composition,
    required PtwShareSource source,
    required PtwShareOutcome outcome,
    required DateTime startedAt,
    String? target,
  }) async {
    final completedAt = _now();
    final record = PtwShareRecord(
      id:
          'share_${completedAt.microsecondsSinceEpoch}_${_snapshot.shareRecords.length}',
      projectId: composition.projectId,
      source: source,
      outcome: outcome,
      story: composition,
      format: ShareFormat.story,
      startedAt: startedAt,
      completedAt: completedAt,
      momentId: composition.momentId,
      target: target,
    );
    final records = [record, ..._snapshot.shareRecords];
    final draft = _snapshot.draft;
    final shouldActivate =
        record.isMeaningfulShare && draft?.id == composition.projectId;
    if (!shouldActivate) {
      await _commit(_snapshot.copyWith(shareRecords: records));
      return maybeProjectById(composition.projectId);
    }

    final existingProject = maybeProjectById(composition.projectId);
    if (existingProject != null) {
      await _commit(
        _snapshot.copyWith(shareRecords: records, clearDraft: true),
      );
      return existingProject;
    }
    if (!draft!.hasValidGoal) throw StateError('Draft goal is invalid');
    final project = PtwProject(
      id: draft.id,
      ownerId: currentUser.id,
      ownerName: currentUser.name,
      ownerHandle: currentUser.handle,
      ownerAvatarAsset: currentUser.avatarAsset,
      goal: draft.goal.trim(),
      doubt: draft.doubt,
      deadline: draft.deadline,
      image: draft.image,
      primaryColor: draft.primaryColor,
      status: PtwProjectStatus.active,
      createdAt: completedAt,
      category: draft.category,
      categoryConfirmed: draft.categoryConfirmed,
      progressMetric: draft.progressMetric,
    );
    final nextCurrent = Map<String, String>.from(
      _snapshot.currentProjectByOwner,
    )..[currentUser.id] = project.id;
    await _commit(
      _snapshot.copyWith(
        currentProjectByOwner: nextCurrent,
        projects: [project, ..._snapshot.projects],
        activatedAt: _snapshot.activatedAt ?? completedAt,
        clearDraft: true,
        shareRecords: records,
      ),
    );
    recoveredProjectImage = null;
    return project;
  }

  Future<PtwProject?> completeShare({
    required ShareCardData card,
    required ShareFormat format,
    required PtwShareSource source,
    required PtwShareOutcome outcome,
    required DateTime startedAt,
    String? momentId,
    String? target,
  }) async {
    final completedAt = _now();
    final record = PtwShareRecord(
      id: 'share_${completedAt.microsecondsSinceEpoch}',
      projectId: card.projectId,
      source: source,
      outcome: outcome,
      card: card,
      format: format,
      startedAt: startedAt,
      completedAt: completedAt,
      momentId: momentId,
      target: target,
    );
    final records = [record, ..._snapshot.shareRecords];
    final draft = _snapshot.draft;
    final shouldActivate =
        record.isMeaningfulShare && draft?.id == card.projectId;
    if (!shouldActivate) {
      await _commit(_snapshot.copyWith(shareRecords: records));
      return maybeProjectById(card.projectId);
    }

    final existingProject = maybeProjectById(card.projectId);
    if (existingProject != null) return existingProject;
    if (!draft!.hasValidGoal) throw StateError('Draft goal is invalid');
    final project = PtwProject(
      id: draft.id,
      ownerId: currentUser.id,
      ownerName: currentUser.name,
      ownerHandle: currentUser.handle,
      ownerAvatarAsset: currentUser.avatarAsset,
      goal: draft.goal.trim(),
      doubt: draft.doubt,
      deadline: draft.deadline,
      image: draft.image,
      primaryColor: draft.primaryColor,
      status: PtwProjectStatus.active,
      createdAt: completedAt,
      category: draft.category,
      categoryConfirmed: draft.categoryConfirmed,
      progressMetric: draft.progressMetric,
    );
    final nextCurrent = Map<String, String>.from(
      _snapshot.currentProjectByOwner,
    )..[currentUser.id] = project.id;
    await _commit(
      _snapshot.copyWith(
        currentProjectByOwner: nextCurrent,
        projects: [project, ..._snapshot.projects],
        activatedAt: _snapshot.activatedAt ?? completedAt,
        clearDraft: true,
        shareRecords: records,
      ),
    );
    recoveredProjectImage = null;
    return project;
  }

  ShareRecommendation recommendedShareFor(String projectId) {
    final project = projectById(projectId);
    final meaningful =
        _snapshot.shareRecords
            .where(
              (record) =>
                  record.projectId == projectId && record.isMeaningfulShare,
            )
            .toList()
          ..sort((a, b) => b.completedAt.compareTo(a.completedAt));
    if (project.status == PtwProjectStatus.completed &&
        !meaningful.any((record) => record.momentId == 'result:$projectId')) {
      return ShareRecommendation(
        event: ShareEvent.goalCompleted,
        template: ShareTemplateType.result,
        momentId: 'result:$projectId',
      );
    }

    final after =
        meaningful.isEmpty
            ? DateTime.fromMillisecondsSinceEpoch(0)
            : meaningful.first.completedAt;
    final latestProof =
        evidenceFor(
          projectId,
        ).where((item) => item.createdAt.isAfter(after)).firstOrNull;
    final latestResponse =
        responsesFor(
          projectId,
        ).where((item) => item.createdAt.isAfter(after)).firstOrNull;
    if (latestProof != null &&
        (latestResponse == null ||
            !latestResponse.createdAt.isAfter(latestProof.createdAt))) {
      return ShareRecommendation(
        event: ShareEvent.milestoneReached,
        template: ShareTemplateType.milestone,
        momentId: 'proof:${latestProof.id}',
      );
    }
    if (latestResponse != null) {
      final isDoubt = latestResponse.side == PtwResponseSide.doubt;
      return ShareRecommendation(
        event: isDoubt ? ShareEvent.newSkeptic : ShareEvent.newSupporter,
        template:
            isDoubt ? ShareTemplateType.criticism : ShareTemplateType.progress,
        momentId: 'response:${latestResponse.id}',
      );
    }
    return const ShareRecommendation(
      event: ShareEvent.manual,
      template: ShareTemplateType.challenge,
    );
  }

  Future<PtwResponse> submitResponse({
    required String projectId,
    required PtwResponseSide side,
    required String message,
  }) async {
    final timestamp = _now();
    final response = PtwResponse(
      id: 'response_${timestamp.microsecondsSinceEpoch}',
      projectId: projectId,
      side: side,
      message: message.trim(),
      createdAt: timestamp,
    );
    await _commit(
      _snapshot.copyWith(responses: [response, ..._snapshot.responses]),
    );
    return response;
  }

  Future<void> markResponsesRead(Iterable<String> ids) async {
    final requestedIds = ids.toSet();
    final unreadIds =
        _snapshot.responses
            .where(
              (response) =>
                  requestedIds.contains(response.id) && !response.isRead,
            )
            .map((response) => response.id)
            .toSet();
    if (unreadIds.isEmpty) return;

    final readAt = _now();
    final updated = [
      for (final response in _snapshot.responses)
        if (unreadIds.contains(response.id))
          response.markRead(readAt)
        else
          response,
    ];
    await _commit(_snapshot.copyWith(responses: updated));
  }

  Future<PtwEvidence> addEvidence({
    required String projectId,
    required String title,
    required String details,
    PtwImageRef? media,
  }) async {
    final timestamp = _now();
    final item = PtwEvidence(
      id: 'evidence_${timestamp.microsecondsSinceEpoch}',
      projectId: projectId,
      title: title.trim(),
      details: details.trim(),
      createdAt: timestamp,
      media: media,
    );
    await _commit(_snapshot.copyWith(evidence: [item, ..._snapshot.evidence]));
    return item;
  }

  Future<PtwProject?> updateProjectMetadata({
    required String projectId,
    PtwProjectCategory? category,
    bool? categoryConfirmed,
    PtwProgressMetric? progressMetric,
    bool clearProgressMetric = false,
  }) async {
    final current = maybeProjectById(projectId);
    if (current == null) return null;
    final updated = current.copyWith(
      category: category,
      categoryConfirmed: categoryConfirmed,
      progressMetric: progressMetric,
      clearProgressMetric: clearProgressMetric,
    );
    await _commit(
      _snapshot.copyWith(
        projects: [
          for (final project in _snapshot.projects)
            if (project.id == projectId) updated else project,
        ],
      ),
    );
    return updated;
  }

  @override
  Future<void> recordShareGenerationEvent(ShareGenerationEvent event) async {
    const maximumLocalEvents = 200;
    final events = [event, ..._snapshot.shareGenerationEvents];
    await _commit(
      _snapshot.copyWith(
        shareGenerationEvents:
            events.length <= maximumLocalEvents
                ? events
                : events.take(maximumLocalEvents).toList(growable: false),
      ),
    );
  }

  Future<void> _commit(PtwPrototypeSnapshot next) async {
    await repository.save(next);
    if (_isDisposed) return;
    _snapshot = next;
    notifyListeners();
  }

  @override
  void dispose() {
    _isDisposed = true;
    super.dispose();
  }

  PtwPrototypeSnapshot _withDistinctPrototypeProofMedia(
    PtwPrototypeSnapshot snapshot,
  ) {
    final projectsById = {
      for (final project in snapshot.projects) project.id: project,
    };
    var changed = false;
    final updated = <PtwEvidence>[];
    for (final proof in snapshot.evidence) {
      final project = projectsById[proof.projectId];
      final shouldReplace =
          project != null &&
          _isPrototypeProof(proof) &&
          proof.media != null &&
          _sameImage(proof.media!, project.image);
      if (!shouldReplace) {
        updated.add(proof);
        continue;
      }
      changed = true;
      updated.add(
        PtwEvidence(
          id: proof.id,
          projectId: proof.projectId,
          title: proof.title,
          details: proof.details,
          createdAt: proof.createdAt,
          media: _alternateProofImageFor(project),
        ),
      );
    }
    return changed ? snapshot.copyWith(evidence: updated) : snapshot;
  }

  PtwPrototypeSnapshot _withChronologicalPrototypeActivity(
    PtwPrototypeSnapshot snapshot,
  ) {
    final demoReferenceTimes = <String, DateTime>{};
    for (final project in snapshot.projects) {
      for (final response in snapshot.responses) {
        if (response.id == 'demo_response_${project.id}_2') {
          demoReferenceTimes[project.id] = response.createdAt.add(
            const Duration(minutes: 47),
          );
          break;
        }
      }
    }
    var evidenceChanged = false;
    final evidence = <PtwEvidence>[
      for (final proof in snapshot.evidence)
        if (_prototypeProofTime(proof, demoReferenceTimes)
            case final createdAt?)
          if (!proof.createdAt.isAtSameMomentAs(createdAt))
            _copyProofWithTime(proof, createdAt)
          else
            proof
        else
          proof,
    ];
    for (var index = 0; index < snapshot.evidence.length; index++) {
      if (!identical(evidence[index], snapshot.evidence[index])) {
        evidenceChanged = true;
        break;
      }
    }

    var responsesChanged = false;
    final responses = <PtwResponse>[
      for (final response in snapshot.responses)
        if (_prototypeResponseTime(response, demoReferenceTimes)
            case final createdAt?)
          if (!response.createdAt.isAtSameMomentAs(createdAt))
            _copyResponseWithTime(response, createdAt)
          else
            response
        else
          response,
    ];
    for (var index = 0; index < snapshot.responses.length; index++) {
      if (!identical(responses[index], snapshot.responses[index])) {
        responsesChanged = true;
        break;
      }
    }

    if (!evidenceChanged && !responsesChanged) return snapshot;
    return snapshot.copyWith(
      evidence: evidenceChanged ? evidence : snapshot.evidence,
      responses: responsesChanged ? responses : snapshot.responses,
    );
  }

  DateTime? _prototypeProofTime(
    PtwEvidence proof,
    Map<String, DateTime> demoReferenceTimes,
  ) {
    if (proof.id == 'evidence_001') {
      return _seedActivityTime.subtract(const Duration(minutes: 10));
    }
    if (proof.id == 'evidence_002') {
      return _seedActivityTime.subtract(const Duration(hours: 2));
    }
    final referenceTime = demoReferenceTimes[proof.projectId];
    if (referenceTime == null) return null;
    if (proof.id == 'demo_proof_${proof.projectId}_1') {
      return referenceTime.subtract(const Duration(minutes: 10));
    }
    if (proof.id == 'demo_proof_${proof.projectId}_2') {
      return referenceTime.subtract(const Duration(hours: 2));
    }
    return null;
  }

  DateTime? _prototypeResponseTime(
    PtwResponse response,
    Map<String, DateTime> demoReferenceTimes,
  ) {
    final seedOffset = switch (response.id) {
      'seed_response_1' => const Duration(minutes: 25),
      'seed_response_2' => const Duration(minutes: 47),
      'seed_response_3' => const Duration(hours: 4),
      _ => null,
    };
    if (seedOffset != null) return _seedActivityTime.subtract(seedOffset);

    final referenceTime = demoReferenceTimes[response.projectId];
    if (referenceTime == null) return null;
    final demoOffset = switch (response.id) {
      final id when id == 'demo_response_${response.projectId}_1' =>
        const Duration(minutes: 25),
      final id when id == 'demo_response_${response.projectId}_2' =>
        const Duration(minutes: 47),
      final id when id == 'demo_response_${response.projectId}_3' =>
        const Duration(hours: 4),
      final id when id == 'demo_response_${response.projectId}_4' =>
        const Duration(hours: 5),
      final id when id == 'demo_response_${response.projectId}_5' =>
        const Duration(days: 1),
      _ => null,
    };
    return demoOffset == null ? null : referenceTime.subtract(demoOffset);
  }

  PtwEvidence _copyProofWithTime(PtwEvidence proof, DateTime createdAt) =>
      PtwEvidence(
        id: proof.id,
        projectId: proof.projectId,
        title: proof.title,
        details: proof.details,
        createdAt: createdAt,
        media: proof.media,
      );

  PtwResponse _copyResponseWithTime(PtwResponse response, DateTime createdAt) =>
      PtwResponse(
        id: response.id,
        projectId: response.projectId,
        side: response.side,
        message: response.message,
        createdAt: createdAt,
        readAt:
            response.readAt != null && response.readAt!.isBefore(createdAt)
                ? createdAt.add(const Duration(minutes: 8))
                : response.readAt,
      );

  bool _isPrototypeProof(PtwEvidence proof) =>
      proof.id.startsWith('demo_proof_') ||
      RegExp(r'^evidence_\d{3}$').hasMatch(proof.id);

  PtwImageRef _alternateProofImageFor(PtwProject project) {
    final candidates =
        curatedImages.map((item) => PtwImageRef.asset(item.asset)).toList();
    if (candidates.isEmpty) return project.image;
    final currentIndex = candidates.indexWhere(
      (candidate) => _sameImage(candidate, project.image),
    );
    for (var offset = 1; offset <= candidates.length; offset++) {
      final index =
          currentIndex < 0
              ? offset - 1
              : (currentIndex + offset) % candidates.length;
      final candidate = candidates[index];
      if (!_sameImage(candidate, project.image)) return candidate;
    }
    return project.image;
  }

  bool _sameImage(PtwImageRef first, PtwImageRef second) =>
      first.source == second.source && first.path == second.path;
}

final class PtwScope extends InheritedNotifier<PtwAppState> {
  const PtwScope({required PtwAppState state, required super.child, super.key})
    : super(notifier: state);

  static PtwAppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<PtwScope>();
    assert(scope != null, 'PtwScope was not found in this context');
    return scope!.notifier!;
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
