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
import '../models/ptw_response.dart';
import '../models/ptw_social_activity.dart';
import '../models/ptw_user.dart';

/// App state backed by a single versioned local prototype snapshot.
final class PtwAppState extends ChangeNotifier {
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
  PtwImageRef? recoveredProjectImage;
  late PtwPrototypeSnapshot _snapshot;

  List<PtwProject> get projects => List.unmodifiable(_snapshot.projects);
  List<PtwResponse> get responses => List.unmodifiable(_snapshot.responses);
  List<PtwEvidence> get evidence => List.unmodifiable(_snapshot.evidence);

  Future<void> load() async {
    isReady = false;
    errorMessage = null;
    try {
      final seed = await _loader.load();
      currentUser = seed.currentUser;
      curatedImages = seed.curatedImages;
      await mediaService.initialize();
      final restored = await repository.load();
      final initial = restored ?? seed.snapshot;
      _snapshot = _withCurrentProjectDemoActivity(
        initial,
        referenceTime: _now(),
      );
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
    _snapshot = seed.snapshot;
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
