import 'package:flutter/widgets.dart';

import '../core/data/mock_json_loader.dart';
import '../core/data/ptw_demo_activity_factory.dart';
import '../core/data/ptw_media_service.dart';
import '../core/data/ptw_prototype_repository.dart';
import '../models/ptw_evidence.dart';
import '../models/ptw_image_ref.dart';
import '../models/ptw_post_background.dart';
import '../models/ptw_project.dart';
import '../models/ptw_prototype_snapshot.dart';
import '../models/ptw_reaction_summary.dart';
import '../models/ptw_response.dart';
import '../models/ptw_social_activity.dart';
import '../models/ptw_user.dart';
import '../features/share/share_models.dart';

/// App state backed by a single versioned local prototype snapshot.
final class PtwAppState extends ChangeNotifier {
  static final _seedActivityTime = DateTime(2026, 8, 2, 12);

  PtwAppState({
    MockJsonLoader loader = const MockJsonLoader(),
    PtwPrototypeRepository? repository,
    PtwMediaService? mediaService,
    DateTime Function()? now,
  }) : _loader = loader,
       repository = repository ?? SharedPreferencesPrototypeRepository(),
       mediaService = mediaService ?? LocalPtwMediaService(),
       _now = now ?? DateTime.now;

  final MockJsonLoader _loader;
  final DateTime Function() _now;
  final PtwPrototypeRepository repository;
  final PtwMediaService mediaService;

  bool isReady = false;
  String? errorMessage;
  late PtwUser currentUser;
  List<PtwPostBackground> curatedImages = [];
  late ShareCatalog shareCatalog;
  PtwImageRef? recoveredProjectImage;
  late PtwPrototypeSnapshot _snapshot;

  List<PtwProject> get projects => List.unmodifiable(_snapshot.projects);
  List<PtwResponse> get responses => List.unmodifiable(_snapshot.responses);
  List<PtwEvidence> get evidence => List.unmodifiable(_snapshot.evidence);
  DateTime get now => _now();

  Future<void> load() async {
    isReady = false;
    errorMessage = null;
    try {
      final seed = await _loader.load();
      currentUser = seed.currentUser;
      curatedImages = seed.curatedImages;
      shareCatalog = seed.shareCatalog;
      await mediaService.initialize();
      final restored = await repository.load();
      final initial = restored ?? seed.snapshot;
      final withDemoActivity = _withCurrentProjectDemoActivity(
        initial,
        referenceTime: _now(),
      );
      final withChronologicalActivity = _withChronologicalPrototypeActivity(
        withDemoActivity,
      );
      _snapshot = _withDistinctPrototypeProofMedia(withChronologicalActivity);
      if (restored == null || !identical(_snapshot, restored)) {
        await repository.save(_snapshot);
      }
      recoveredProjectImage = await mediaService.recoverLostProjectImage();
      isReady = true;
    } catch (error) {
      errorMessage = error.toString();
    }
    notifyListeners();
  }

  Future<void> reset() async {
    await repository.reset();
    final seed = await _loader.load();
    currentUser = seed.currentUser;
    curatedImages = seed.curatedImages;
    shareCatalog = seed.shareCatalog;
    _snapshot = _withDistinctPrototypeProofMedia(
      _withChronologicalPrototypeActivity(seed.snapshot),
    );
    await repository.save(_snapshot);
    recoveredProjectImage = null;
    errorMessage = null;
    isReady = true;
    notifyListeners();
  }

  PtwProject get currentProject {
    final id = _snapshot.currentProjectByOwner[currentUser.id];
    return projectById(id!);
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

  Future<PtwProject> createProject({
    required String goal,
    required DateTime deadline,
    required PtwImageRef image,
    required int primaryColor,
  }) async {
    final timestamp = _now();
    final project = PtwProject(
      id: 'project_${timestamp.microsecondsSinceEpoch}',
      ownerId: currentUser.id,
      ownerName: currentUser.name,
      ownerHandle: currentUser.handle,
      ownerAvatarAsset: currentUser.avatarAsset,
      goal: goal.trim(),
      deadline: DateTime(deadline.year, deadline.month, deadline.day),
      image: image,
      primaryColor: primaryColor,
      status: PtwProjectStatus.active,
      createdAt: timestamp,
    );
    final nextCurrent = Map<String, String>.from(
      _snapshot.currentProjectByOwner,
    )..[currentUser.id] = project.id;
    final demoActivity = PtwDemoActivityFactory.forProject(
      project: project,
      referenceTime: timestamp,
      proofImage: _alternateProofImageFor(project),
    );
    await _commit(
      _snapshot.copyWith(
        currentProjectByOwner: nextCurrent,
        projects: [project, ..._snapshot.projects],
        responses: [...demoActivity.responses, ..._snapshot.responses],
        evidence: [...demoActivity.evidence, ..._snapshot.evidence],
      ),
    );
    recoveredProjectImage = null;
    return project;
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

  Future<void> _commit(PtwPrototypeSnapshot next) async {
    await repository.save(next);
    _snapshot = next;
    notifyListeners();
  }

  PtwPrototypeSnapshot _withCurrentProjectDemoActivity(
    PtwPrototypeSnapshot snapshot, {
    required DateTime referenceTime,
  }) {
    final currentProjectId = snapshot.currentProjectByOwner[currentUser.id];
    if (currentProjectId == null) return snapshot;
    final project = snapshot.projects.where(
      (item) => item.id == currentProjectId,
    );
    if (project.isEmpty) return snapshot;

    final needsResponses =
        !snapshot.responses.any((item) => item.projectId == currentProjectId);
    final needsEvidence =
        !snapshot.evidence.any((item) => item.projectId == currentProjectId);
    if (!needsResponses && !needsEvidence) return snapshot;

    final demoActivity = PtwDemoActivityFactory.forProject(
      project: project.single,
      referenceTime: referenceTime,
      proofImage: _alternateProofImageFor(project.single),
    );
    return snapshot.copyWith(
      responses:
          needsResponses
              ? [...demoActivity.responses, ...snapshot.responses]
              : snapshot.responses,
      evidence:
          needsEvidence
              ? [...demoActivity.evidence, ...snapshot.evidence]
              : snapshot.evidence,
    );
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
