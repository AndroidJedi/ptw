import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/data/ptw_media_service.dart';
import '../../core/theme/ptw_colors.dart';
import '../../features/share/share_models.dart';
import '../../features/share/share_face_safety.dart';
import '../../features/share/share_generation.dart';
import '../../features/share/share_service.dart';
import '../../generated_share_editor/generated_share_editor.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_share_record.dart';
import '../../models/ptw_share_generation_event.dart';
import '../../models/ptw_story_composition.dart';
import '../../state/ptw_app_state.dart';
import 'instagram_story_guide.dart';
import 'ptw_generated_story_adapter.dart';

/// The one creator-facing share runtime used by onboarding and every project
/// share entry. Legacy card formats remain decodable in share history only.
final class ShareStoryPreviewScreen extends StatefulWidget {
  const ShareStoryPreviewScreen.project({
    required this.projectId,
    required this.source,
    super.key,
    this.event,
    this.momentId,
  }) : isDraft = false;

  const ShareStoryPreviewScreen.draft({required this.source, super.key})
    : isDraft = true,
      projectId = null,
      event = ShareEvent.challengeCreated,
      momentId = null;

  final bool isDraft;
  final String? projectId;
  final PtwShareSource source;
  final ShareEvent? event;

  final String? momentId;

  @override
  State<ShareStoryPreviewScreen> createState() =>
      _ShareStoryPreviewScreenState();
}

final class _ShareStoryPreviewScreenState
    extends State<ShareStoryPreviewScreen> {
  final _assetGenerator = const SharePngExporter();
  final _adapter = const PtwGeneratedStoryAdapter();
  final _candidateGenerator = const PtwShareCandidateGenerator();
  final _journeyRecommender = const PtwJourneyRecommender();
  final _categorySuggester = const PtwProjectCategorySuggester();
  final _faceSafety = createShareFaceSafetyService();
  ShareEditorController? _controller;
  ShareEditorValue? _lastObservedValue;
  ShareEditorContent? _content;
  PtwStoryComposition? _baseComposition;
  PtwAppState? _appState;
  PtwProject? _subject;
  Timer? _autosaveTimer;
  String? _activatedProjectId;
  bool _copied = false;
  bool _busy = false;
  bool _initialized = false;
  bool _headlineEventRecorded = false;
  bool _photoEventRecorded = false;
  late DateTime _generationStartedAt;
  late String _generationSessionId;
  ShareEvent _generationEvent = ShareEvent.manual;
  String? _generationMomentId;
  ShareJourneyState _journeyState = ShareJourneyState.beginning;
  PtwProjectCategory _category = PtwProjectCategory.other;
  int _regenerationIndex = 0;
  List<ShareCandidate> _candidates = const [];
  ShareCandidate? _selectedCandidate;
  bool _stickersAllowed = false;
  _ShareBuilderStep _step = _ShareBuilderStep.confirmJourney;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = PtwScope.of(context);
    _appState = state;
    if (!_initialized) _initializeGeneration(state);
  }

  void _initializeGeneration(PtwAppState state) {
    _initialized = true;
    final project = _storyProject(state);
    if (project == null) return;
    _subject = project;
    var event = widget.event ?? ShareEvent.manual;
    var momentId = widget.momentId;
    if (!widget.isDraft && widget.source == PtwShareSource.launch) {
      final recommendation = state.recommendedShareFor(project.id);
      event = recommendation.event;
      momentId = recommendation.momentId;
    }
    _generationEvent = event;
    _generationMomentId = momentId;
    _generationStartedAt = state.now;
    _generationSessionId =
        'generation_${project.id}_${_generationStartedAt.microsecondsSinceEpoch}';
    _category = project.category ?? _categorySuggester.suggest(project.goal);
    _journeyState = _journeyRecommender.recommend(
      project: project,
      evidence: state.evidenceFor(project.id),
      shares: state.shareRecordsFor(project.id),
    );

    final saved = state.draft?.storyComposition;
    if (widget.isDraft &&
        saved?.projectId == project.id &&
        saved?.journeyState != null &&
        saved?.templateId != null) {
      _journeyState = ShareJourneyState.values.firstWhere(
        (item) => item.name == saved!.journeyState,
        orElse: () => _journeyState,
      );
      _baseComposition = saved;
      _content = _adapter.content(project: project, composition: saved!);
      _controller = ShareEditorController(
        theme: state.shareEditorTheme,
        content: _content!,
        mode: ShareEditorMode.runtime,
        initialValue: _adapter.value(
          theme: state.shareEditorTheme,
          content: _content!,
          composition: saved,
          project: project,
        ),
      )..addListener(_onCompositionChanged);
      _step = _ShareBuilderStep.edit;
    }
    unawaited(
      _recordGenerationEvent(ShareGenerationEventType.generationStarted),
    );
  }

  PtwProject? _storyProject(PtwAppState state) {
    if (!widget.isDraft) return state.maybeProjectById(widget.projectId!);
    final draft = state.draft;
    if (draft == null || !draft.hasValidGoal) return null;
    return PtwProject(
      id: draft.id,
      ownerId: state.currentUser.id,
      ownerName: state.currentUser.name,
      ownerHandle: state.currentUser.handle,
      ownerAvatarAsset: state.currentUser.avatarAsset,
      goal: draft.goal,
      doubt: draft.doubt,
      deadline: draft.deadline,
      image: draft.image,
      primaryColor: draft.primaryColor,
      status: PtwProjectStatus.active,
      createdAt: draft.createdAt,
      category: draft.category,
      categoryConfirmed: draft.categoryConfirmed,
      progressMetric: draft.progressMetric,
    );
  }

  Future<void> _confirmJourneyAndGenerate() async {
    final state = _appState;
    var project = _subject;
    if (state == null || project == null || _busy) return;
    setState(() => _busy = true);
    try {
      if (widget.isDraft) {
        final draft = state.draft;
        if (draft != null) {
          await state.saveDraft(
            goal: draft.goal,
            doubt: draft.doubt ?? '',
            deadline: draft.deadline,
            image: draft.image,
            primaryColor: draft.primaryColor,
            category: _category,
            categoryConfirmed: true,
            progressMetric: draft.progressMetric,
          );
          project = project.copyWith(
            category: _category,
            categoryConfirmed: true,
          );
        }
      } else if (!project.categoryConfirmed || project.category != _category) {
        project =
            await state.updateProjectMetadata(
              projectId: project.id,
              category: _category,
              categoryConfirmed: true,
            ) ??
            project;
      }
      _subject = project;
      await _recordGenerationEvent(ShareGenerationEventType.stateConfirmed);
      final evidence = state.evidenceFor(project.id);
      final currentMedia =
          evidence
              .map((item) => item.media)
              .whereType<PtwImageRef>()
              .firstOrNull ??
          project.image;
      _stickersAllowed = await _faceSafety.canUseSemanticStickers(
        currentMedia,
        resolveFilePath: state.mediaService.resolveFilePath,
      );
      _generateCandidates();
      await _recordGenerationEvent(ShareGenerationEventType.candidatesShown);
      if (mounted) {
        setState(() {
          _step = _ShareBuilderStep.candidates;
          _busy = false;
        });
      }
    } on Object {
      if (!mounted) return;
      setState(() => _busy = false);
      _message('Could not generate those options. Try again.');
    }
  }

  void _generateCandidates() {
    final state = _appState!;
    final project = _subject!;
    _candidates = _candidateGenerator.generate(
      ShareGenerationContext(
        theme: state.shareEditorTheme,
        project: project,
        evidence: state.evidenceFor(project.id),
        responses: state.responsesFor(project.id),
        previousShares: state.shareRecordsFor(project.id),
        event: _generationEvent,
        momentId: _generationMomentId,
        journeyState: _journeyState,
        now: state.now,
        regenerationIndex: _regenerationIndex,
        stickersAllowed: _stickersAllowed,
      ),
    );
  }

  Future<void> _regenerateCandidates() async {
    if (_busy) return;
    final controller = _controller;
    controller?.removeListener(_onCompositionChanged);
    controller?.dispose();
    _controller = null;
    _content = null;
    _baseComposition = null;
    _selectedCandidate = null;
    _regenerationIndex++;
    _generateCandidates();
    setState(() => _step = _ShareBuilderStep.candidates);
    await _recordGenerationEvent(ShareGenerationEventType.optionsRegenerated);
    await _recordGenerationEvent(ShareGenerationEventType.candidatesShown);
  }

  void _selectCandidate(ShareCandidate candidate) {
    final state = _appState!;
    final project = _subject!;
    final base = _adapter.createBase(
      project: project,
      event: _generationEvent,
      momentId: _generationMomentId,
      now: state.now,
      candidate: candidate,
    );
    final content = _adapter.content(
      project: project,
      composition: base,
      candidate: candidate,
    );
    final value = _adapter.value(
      theme: state.shareEditorTheme,
      content: content,
      composition: base,
      project: project,
      candidate: candidate,
    );
    final oldController = _controller;
    oldController?.removeListener(_onCompositionChanged);
    oldController?.dispose();
    _selectedCandidate = candidate;
    _baseComposition = base;
    _content = content;
    _controller = ShareEditorController(
      theme: state.shareEditorTheme,
      content: content,
      mode: ShareEditorMode.runtime,
      initialValue: value,
    )..addListener(_onCompositionChanged);
    _lastObservedValue = value;
    _headlineEventRecorded = false;
    _photoEventRecorded = false;
    setState(() => _step = _ShareBuilderStep.edit);
    unawaited(
      _recordGenerationEvent(
        ShareGenerationEventType.candidateSelected,
        candidateId: candidate.id,
      ),
    );
    if (widget.isDraft) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final current = _currentComposition;
        if (mounted && current != null) {
          unawaited(state.saveDraftStory(current));
        }
      });
    }
  }

  ({
    PtwStoryComposition composition,
    ShareEditorContent content,
    ShareEditorValue value,
  })
  _previewFor(ShareCandidate candidate) {
    final state = _appState!;
    final project = _subject!;
    final composition = _adapter.createBase(
      project: project,
      event: _generationEvent,
      momentId: _generationMomentId,
      now: state.now,
      candidate: candidate,
    );
    final content = _adapter.content(
      project: project,
      composition: composition,
      candidate: candidate,
    );
    return (
      composition: composition,
      content: content,
      value: _adapter.value(
        theme: state.shareEditorTheme,
        content: content,
        composition: composition,
        project: project,
        candidate: candidate,
      ),
    );
  }

  Future<void> _recordGenerationEvent(
    ShareGenerationEventType type, {
    String? candidateId,
  }) async {
    final state = _appState;
    final project = _subject;
    if (state == null || project == null) return;
    final timestamp = state.now;
    await state.recordShareGenerationEvent(
      ShareGenerationEvent(
        id: 'event_${timestamp.microsecondsSinceEpoch}_${type.name}',
        sessionId: _generationSessionId,
        projectId: project.id,
        type: type,
        timestamp: timestamp,
        candidateId: candidateId ?? _selectedCandidate?.id,
        journeyState: _journeyState.name,
        elapsedMilliseconds:
            timestamp.difference(_generationStartedAt).inMilliseconds,
      ),
    );
  }

  void _onCompositionChanged() {
    if (!mounted) return;
    final currentValue = _controller?.value;
    final previousValue = _lastObservedValue;
    if (currentValue != null && previousValue != null) {
      if (!_headlineEventRecorded &&
          currentValue.layerValues['headline'] !=
              previousValue.layerValues['headline']) {
        _headlineEventRecorded = true;
        unawaited(
          _recordGenerationEvent(ShareGenerationEventType.headlineEdited),
        );
      }
      final currentImage = currentValue.backgroundEdit.image;
      final previousImage = previousValue.backgroundEdit.image;
      if (!_photoEventRecorded &&
          (currentImage?.path != previousImage?.path ||
              currentValue.backgroundEdit.alignmentX !=
                  previousValue.backgroundEdit.alignmentX ||
              currentValue.backgroundEdit.alignmentY !=
                  previousValue.backgroundEdit.alignmentY ||
              currentValue.backgroundEdit.zoom !=
                  previousValue.backgroundEdit.zoom ||
              currentValue.layerValues['current_media'] !=
                  previousValue.layerValues['current_media'])) {
        _photoEventRecorded = true;
        unawaited(
          _recordGenerationEvent(ShareGenerationEventType.photoChanged),
        );
      }
      _lastObservedValue = currentValue;
    }
    setState(() {});
    if (!widget.isDraft || _appState?.draft == null) return;
    _autosaveTimer?.cancel();
    _autosaveTimer = Timer(const Duration(milliseconds: 300), () {
      final controller = _controller;
      final state = _appState;
      if (controller != null && state?.draft != null) {
        final composition = _currentComposition;
        if (composition != null) unawaited(state!.saveDraftStory(composition));
      }
    });
  }

  Future<void> _persistDraftNow() async {
    _autosaveTimer?.cancel();
    final controller = _controller;
    final state = _appState;
    if (widget.isDraft && controller != null && state?.draft != null) {
      final composition = _currentComposition;
      if (composition != null) await state!.saveDraftStory(composition);
    }
  }

  PtwStoryComposition? get _currentComposition {
    final controller = _controller;
    final state = _appState;
    final base = _baseComposition;
    if (controller == null || state == null || base == null) return null;
    return _adapter.composition(
      theme: state.shareEditorTheme,
      base: base,
      value: controller.value,
      updatedAt: state.now,
    );
  }

  @override
  void dispose() {
    _autosaveTimer?.cancel();
    final controller = _controller;
    controller?.removeListener(_onCompositionChanged);
    controller?.dispose();
    super.dispose();
  }

  Future<bool> _copyAndRecord({bool announce = true}) async {
    final controller = _controller;
    final state = _appState;
    final composition = _currentComposition;
    if (controller == null || state == null || composition == null) {
      return false;
    }
    await _persistDraftNow();
    final startedAt = state.now;
    try {
      await Clipboard.setData(ClipboardData(text: composition.publicLink));
      final project = await state.completeStoryShare(
        composition: composition,
        source: widget.source,
        outcome: PtwShareOutcome.copied,
        startedAt: startedAt,
        target: 'clipboard',
      );
      if (!mounted) return true;
      setState(() {
        _copied = true;
        _activatedProjectId = project?.id ?? _activatedProjectId;
      });
      if (announce) _message('PTW link copied');
      return true;
    } on Object {
      try {
        await state.completeStoryShare(
          composition: composition,
          source: widget.source,
          outcome: PtwShareOutcome.failed,
          startedAt: startedAt,
          target: 'clipboard',
        );
      } on Object {
        // Keep the live composition even when attempt persistence also fails.
      }
      if (mounted && announce) _message('The link could not be copied.');
      return false;
    }
  }

  Future<void> _copyPressed() async {
    if (_busy) return;
    setState(() => _busy = true);
    await _copyAndRecord();
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _startShare() async {
    if (_busy || _controller == null) return;
    setState(() => _busy = true);
    var mayContinue = true;
    if (!_copied) {
      final copied = await _copyAndRecord(announce: false);
      if (!copied && mounted) mayContinue = await _clipboardFailureChoice();
    }
    if (!mounted) return;
    setState(() => _busy = false);
    if (!mayContinue) return;
    final shared = await showInstagramStoryGuide(
      context: context,
      onShare: _shareFromGuide,
      onCopy: () => _copyAndRecord(),
    );
    if (shared && mounted) _finishShare();
  }

  Future<bool> _clipboardFailureChoice() async {
    final choice = await showDialog<_ClipboardFailureChoice>(
      context: context,
      builder:
          (dialogContext) => AlertDialog(
            title: const Text('Couldn’t copy the link'),
            content: const Text(
              'Retry so the link is ready to paste in Instagram, or continue '
              'and add it yourself.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancel'),
              ),
              TextButton(
                key: const ValueKey('continue_without_link'),
                onPressed:
                    () => Navigator.pop(
                      dialogContext,
                      _ClipboardFailureChoice.continueWithoutLink,
                    ),
                child: const Text('Continue without link'),
              ),
              FilledButton(
                key: const ValueKey('retry_copy_link'),
                onPressed:
                    () => Navigator.pop(
                      dialogContext,
                      _ClipboardFailureChoice.retry,
                    ),
                child: const Text('Retry'),
              ),
            ],
          ),
    );
    if (choice == _ClipboardFailureChoice.continueWithoutLink) return true;
    if (choice != _ClipboardFailureChoice.retry) return false;
    return _copyAndRecord();
  }

  Future<InstagramGuideShareResult> _shareFromGuide(Rect origin) async {
    final controller = _controller!;
    final state = _appState!;
    final content = _content!;
    final composition = _currentComposition!;
    final startedAt = state.now;
    try {
      final png = await _assetGenerator.generate(
        context: context,
        theme: state.shareEditorTheme,
        content: content,
        value: controller.value,
        imageResolver: _resolveImage,
        fileName: 'ptw_${composition.projectId}_story.png',
      );
      await _recordGenerationEvent(ShareGenerationEventType.exportCompleted);
      if (!mounted) {
        return const InstagramGuideShareResult(
          InstagramGuideShareStatus.failed,
        );
      }
      await _recordGenerationEvent(ShareGenerationEventType.shareInvoked);
      final result = await state.shareService.share(
        asset: ShareAsset(
          bytes: png.bytes,
          format: ShareFormat.story,
          fileName: png.fileName,
        ),
        text:
            '${composition.caption}\n\n'
            '${composition.publicLink}',
        sharePositionOrigin: origin,
      );
      final outcome = switch (result.status) {
        PtwShareResultStatus.success => PtwShareOutcome.success,
        PtwShareResultStatus.dismissed => PtwShareOutcome.dismissed,
        PtwShareResultStatus.unavailable => PtwShareOutcome.unavailable,
      };
      final project = await state.completeStoryShare(
        composition: composition,
        source: widget.source,
        outcome: outcome,
        startedAt: startedAt,
        target: result.target,
      );
      if (mounted && project != null) _activatedProjectId = project.id;
      return switch (result.status) {
        PtwShareResultStatus.success => const InstagramGuideShareResult(
          InstagramGuideShareStatus.success,
        ),
        PtwShareResultStatus.dismissed => const InstagramGuideShareResult(
          InstagramGuideShareStatus.dismissed,
        ),
        PtwShareResultStatus.unavailable => const InstagramGuideShareResult(
          InstagramGuideShareStatus.unavailable,
          message: 'Sharing could not be confirmed. Retry or copy the link.',
        ),
      };
    } on Object {
      try {
        await state.completeStoryShare(
          composition: composition,
          source: widget.source,
          outcome: PtwShareOutcome.failed,
          startedAt: startedAt,
        );
      } on Object {
        // The editable Story remains available even if persistence fails.
      }
      return const InstagramGuideShareResult(
        InstagramGuideShareStatus.failed,
        message: 'Could not prepare the Story. Retry or copy the link.',
      );
    }
  }

  ImageProvider<Object>? _resolveImage(ShareImageValue image) {
    if (image.source != ShareImageSource.file) {
      return defaultShareImageResolver(image);
    }
    final state = _appState;
    final path = image.path;
    if (state == null || path == null) return null;
    return FileImage(
      File(state.mediaService.resolveFilePath(PtwImageRef.file(path))),
    );
  }

  Future<ShareImageValue?> _pickEditorImage(ShareImageRequest request) async {
    final state = _appState;
    if (state == null) return null;
    try {
      final selected = await state.mediaService.pickShareImage(switch (request
          .purpose) {
        ShareImagePurpose.layer => PtwShareImagePurpose.layer,
        ShareImagePurpose.background => PtwShareImagePurpose.background,
        ShareImagePurpose.decoration => PtwShareImagePurpose.decoration,
      });
      if (selected == null) return null;
      final stickersAllowed = await _faceSafety.canUseSemanticStickers(
        selected,
        resolveFilePath: state.mediaService.resolveFilePath,
      );
      _stickersAllowed = stickersAllowed;
      if (!stickersAllowed) _controller?.suppressSemanticStickers();
      return switch (selected.source) {
        PtwImageSource.asset => ShareImageValue.asset(selected.path),
        PtwImageSource.file => ShareImageValue.file(selected.path),
      };
    } on PtwMediaException catch (error) {
      if (mounted) _message(error.message);
      return null;
    } on Object {
      if (mounted) _message('That image could not be opened.');
      return null;
    }
  }

  void _finishShare() {
    final projectId =
        _activatedProjectId ??
        _subject?.id ??
        _appState?.currentProjectOrNull?.id;
    if (projectId == null) return;
    if (!widget.isDraft &&
        widget.source != PtwShareSource.launch &&
        context.canPop()) {
      context.pop();
      return;
    }
    context.go('/projects/$projectId${widget.isDraft ? '?activated=1' : ''}');
  }

  Future<void> _close() async {
    await _persistDraftNow();
    if (!mounted) return;
    final projectId =
        _activatedProjectId ??
        (!widget.isDraft ? _subject?.id : _appState?.currentProjectOrNull?.id);
    if (projectId != null) {
      if (!widget.isDraft &&
          widget.source != PtwShareSource.launch &&
          context.canPop()) {
        context.pop();
      } else {
        context.go('/projects/$projectId');
      }
      return;
    }
    context.go('/onboarding');
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  Future<void> _openShareStep() async {
    final composition = _currentComposition;
    if (composition == null || composition.headline.trim().isEmpty) {
      _message('Add a short headline before continuing.');
      return;
    }
    await _persistDraftNow();
    if (!mounted) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => _step = _ShareBuilderStep.share);
  }

  void _backToBuilder() {
    if (_busy) return;
    setState(() => _step = _ShareBuilderStep.edit);
  }

  @override
  Widget build(BuildContext context) {
    final state = _appState;
    if (state == null || _subject == null) {
      return const Scaffold(
        body: Center(child: Text('This Story is no longer available.')),
      );
    }
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        if (_step == _ShareBuilderStep.share) {
          _backToBuilder();
        } else if (_step == _ShareBuilderStep.edit) {
          setState(() => _step = _ShareBuilderStep.candidates);
        } else if (_step == _ShareBuilderStep.candidates) {
          setState(() => _step = _ShareBuilderStep.confirmJourney);
        } else {
          unawaited(_close());
        }
      },
      child: Scaffold(
        key: const ValueKey(ComponentIds.shareScreen),
        backgroundColor: const Color(0xFF0E1423),
        body: SafeArea(
          child: switch (_step) {
            _ShareBuilderStep.confirmJourney => _JourneyConfirmation(
              selectedJourney: _journeyState,
              selectedCategory: _category,
              categoryConfirmed: _subject!.categoryConfirmed,
              busy: _busy,
              onJourneyChanged:
                  (value) => setState(() => _journeyState = value),
              onCategoryChanged: (value) => setState(() => _category = value),
              onClose: () => unawaited(_close()),
              onContinue: () => unawaited(_confirmJourneyAndGenerate()),
            ),
            _ShareBuilderStep.candidates => _CandidateSelection(
              candidates: _candidates,
              theme: state.shareEditorTheme,
              previewFor: _previewFor,
              imageResolver: _resolveImage,
              onBack:
                  () =>
                      setState(() => _step = _ShareBuilderStep.confirmJourney),
              onSelect: _selectCandidate,
              onRegenerate: () => unawaited(_regenerateCandidates()),
            ),
            _ShareBuilderStep.edit => GeneratedShareEditor(
              theme: state.shareEditorTheme,
              content: _content!,
              controller: _controller!,
              imagePicker: _pickEditorImage,
              imageResolver: _resolveImage,
              title: _journeyState.label.toUpperCase(),
              onGenerateAnother: () => unawaited(_regenerateCandidates()),
              onClose:
                  () => setState(() => _step = _ShareBuilderStep.candidates),
              onContinue: () => unawaited(_openShareStep()),
              onLockedFeatureTap:
                  (feature) =>
                      _message('${feature.label} requires premium access.'),
            ),
            _ShareBuilderStep.share => _ShareHandoff(
              controller: _controller!,
              theme: state.shareEditorTheme,
              content: _content!,
              composition: _currentComposition!,
              imageResolver: _resolveImage,
              copied: _copied,
              busy: _busy,
              onBack: _backToBuilder,
              onCopy: _copyPressed,
              onShare: _startShare,
            ),
          },
        ),
      ),
    );
  }
}

extension _FirstImageOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}

enum _ShareBuilderStep { confirmJourney, candidates, edit, share }

final class _JourneyConfirmation extends StatelessWidget {
  const _JourneyConfirmation({
    required this.selectedJourney,
    required this.selectedCategory,
    required this.categoryConfirmed,
    required this.busy,
    required this.onJourneyChanged,
    required this.onCategoryChanged,
    required this.onClose,
    required this.onContinue,
  });

  final ShareJourneyState selectedJourney;
  final PtwProjectCategory selectedCategory;
  final bool categoryConfirmed;
  final bool busy;
  final ValueChanged<ShareJourneyState> onJourneyChanged;
  final ValueChanged<PtwProjectCategory> onCategoryChanged;
  final VoidCallback onClose;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      SizedBox(
        height: 56,
        child: Row(
          children: [
            IconButton(
              key: const ValueKey('journey_close'),
              onPressed: busy ? null : onClose,
              color: Colors.white,
              icon: const Icon(Icons.close_rounded),
            ),
            const Expanded(
              child: Text(
                'TODAY’S CHAPTER',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontFamily: 'PtwLilitaOne',
                  fontSize: 21,
                  letterSpacing: 0.7,
                ),
              ),
            ),
            const SizedBox(width: 48),
          ],
        ),
      ),
      Expanded(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 30),
          children: [
            const Text(
              'Where are you in the journey today?',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 28,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'PTW suggested ${selectedJourney.label}. Confirm it or choose the honest stage.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 14,
                height: 1.35,
              ),
            ),
            const SizedBox(height: 22),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 9,
              runSpacing: 9,
              children: [
                for (final journey in ShareJourneyState.values)
                  if (journey != ShareJourneyState.unassigned)
                    ChoiceChip(
                      key: ValueKey('journey_${journey.name}'),
                      label: Text(journey.label),
                      selected: journey == selectedJourney,
                      onSelected: (_) => onJourneyChanged(journey),
                    ),
              ],
            ),
            const SizedBox(height: 28),
            Text(
              categoryConfirmed
                  ? 'SEMANTIC STYLE · ${selectedCategory.label.toUpperCase()}'
                  : 'CONFIRM THE JOURNEY TOPIC',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
                fontWeight: FontWeight.w900,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            if (!categoryConfirmed)
              Wrap(
                alignment: WrapAlignment.center,
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final category in PtwProjectCategory.values)
                    ChoiceChip(
                      key: ValueKey('share_category_${category.name}'),
                      label: Text(category.label),
                      selected: category == selectedCategory,
                      onSelected: (_) => onCategoryChanged(category),
                    ),
                ],
              ),
            const SizedBox(height: 30),
            SizedBox(
              height: 56,
              child: FilledButton.icon(
                key: const ValueKey('confirm_journey'),
                onPressed: busy ? null : onContinue,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFF4066E),
                  foregroundColor: Colors.white,
                  shape: const StadiumBorder(),
                ),
                icon:
                    busy
                        ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                        : const Icon(Icons.auto_awesome_rounded),
                label: Text(
                  busy ? 'Generating…' : 'Show me 3 options',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

final class _CandidateSelection extends StatelessWidget {
  const _CandidateSelection({
    required this.candidates,
    required this.theme,
    required this.previewFor,
    required this.imageResolver,
    required this.onBack,
    required this.onSelect,
    required this.onRegenerate,
  });

  final List<ShareCandidate> candidates;
  final ShareThemeConfig theme;
  final ({
    PtwStoryComposition composition,
    ShareEditorContent content,
    ShareEditorValue value,
  })
  Function(ShareCandidate candidate)
  previewFor;
  final ShareImageProviderResolver imageResolver;
  final VoidCallback onBack;
  final ValueChanged<ShareCandidate> onSelect;
  final VoidCallback onRegenerate;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      SizedBox(
        height: 58,
        child: Row(
          children: [
            IconButton(
              key: const ValueKey('candidate_back'),
              onPressed: onBack,
              color: Colors.white,
              icon: const Icon(Icons.arrow_back_rounded),
            ),
            const Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'CHOOSE YOUR STORY',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white,
                      fontFamily: 'PtwLilitaOne',
                      fontSize: 21,
                    ),
                  ),
                  Text(
                    '3 different families · 3 different styles',
                    style: TextStyle(color: Colors.white60, fontSize: 11),
                  ),
                ],
              ),
            ),
            IconButton(
              key: const ValueKey('candidate_regenerate'),
              tooltip: 'New options',
              onPressed: onRegenerate,
              color: const Color(0xFFFFE557),
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
      ),
      Expanded(
        child: ListView.separated(
          key: const ValueKey('share_candidate_list'),
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(18, 10, 18, 18),
          itemCount: candidates.length,
          separatorBuilder: (_, __) => const SizedBox(width: 14),
          itemBuilder: (context, index) {
            final candidate = candidates[index];
            final preview = previewFor(candidate);
            return SizedBox(
              width: 238,
              child: Material(
                color: const Color(0xFF1B2741),
                borderRadius: BorderRadius.circular(24),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  key: ValueKey('share_candidate_${candidate.id}'),
                  onTap: () => onSelect(candidate),
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      children: [
                        Expanded(
                          child: AspectRatio(
                            aspectRatio:
                                theme.canvas.width / theme.canvas.height,
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(16),
                              child: GeneratedShareRenderer(
                                theme: theme,
                                content: preview.content,
                                value: preview.value,
                                imageResolver: imageResolver,
                                showSelection: false,
                                interactionEnabled: false,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          candidate.label,
                          maxLines: 2,
                          textAlign: TextAlign.center,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            onPressed: () => onSelect(candidate),
                            style: FilledButton.styleFrom(
                              backgroundColor: const Color(0xFFF4066E),
                              foregroundColor: Colors.white,
                            ),
                            child: const Text('Use this'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    ],
  );
}

enum _ClipboardFailureChoice { retry, continueWithoutLink }

final class _ShareHandoff extends StatelessWidget {
  const _ShareHandoff({
    required this.controller,
    required this.theme,
    required this.content,
    required this.composition,
    required this.imageResolver,
    required this.copied,
    required this.busy,
    required this.onBack,
    required this.onCopy,
    required this.onShare,
  });

  final ShareEditorController controller;
  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final PtwStoryComposition composition;
  final ShareImageProviderResolver imageResolver;
  final bool copied;
  final bool busy;
  final VoidCallback onBack;
  final VoidCallback onCopy;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      SizedBox(
        height: 52,
        child: Row(
          children: [
            IconButton(
              key: const ValueKey(ComponentIds.shareBack),
              tooltip: 'Back to builder',
              onPressed: busy ? null : onBack,
              color: PtwColors.textOnAccent,
              icon: const Icon(Icons.arrow_back_rounded, size: 28),
            ),
            const Expanded(
              child: Text(
                'READY TO SHARE',
                key: ValueKey(ComponentIds.shareTitle),
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: PtwColors.textOnAccent,
                  fontFamily: 'PtwLilitaOne',
                  fontSize: 21,
                  letterSpacing: 0.7,
                ),
              ),
            ),
            const SizedBox(width: 48),
          ],
        ),
      ),
      Expanded(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 5, 18, 24),
          children: [
            const Text(
              'Your Story is ready. Copy the link, then share it.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PtwColors.softWhite,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 190),
                child: AspectRatio(
                  aspectRatio: theme.canvas.width / theme.canvas.height,
                  child: ClipRRect(
                    key: const ValueKey(ComponentIds.sharePreview),
                    borderRadius: BorderRadius.circular(24),
                    child: AnimatedBuilder(
                      animation: controller,
                      builder:
                          (_, __) => GeneratedShareRenderer(
                            theme: theme,
                            content: content,
                            value: controller.value,
                            imageResolver: imageResolver,
                            showSelection: false,
                          ),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            _ShareActions(
              publicLink: composition.publicLink,
              copied: copied,
              busy: busy,
              onCopy: onCopy,
              onShare: onShare,
            ),
          ],
        ),
      ),
    ],
  );
}

final class _ShareActions extends StatelessWidget {
  const _ShareActions({
    required this.publicLink,
    required this.copied,
    required this.busy,
    required this.onCopy,
    required this.onShare,
  });

  final String publicLink;
  final bool copied;
  final bool busy;
  final VoidCallback onCopy;
  final VoidCallback onShare;

  String get shortLink => publicLink.replaceFirst('https://', '');

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.fromLTRB(18, 20, 18, 18),
    decoration: BoxDecoration(
      color: const Color(0xFF171F36),
      borderRadius: BorderRadius.circular(26),
      border: Border.all(color: const Color(0xFF27314E)),
    ),
    child: Column(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _StepNumber(1),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Copy your PTW link',
                    style: TextStyle(
                      color: PtwColors.textOnAccent,
                      fontSize: 18,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    shortLink,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PtwColors.softWhite,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(
              key: const ValueKey(ComponentIds.shareCopyLink),
              onPressed: busy ? null : onCopy,
              style: OutlinedButton.styleFrom(
                foregroundColor:
                    copied ? PtwColors.accentMint : PtwColors.accentPink,
                side: BorderSide(
                  color: copied ? PtwColors.accentMint : PtwColors.accentPink,
                  width: 2,
                ),
                visualDensity: VisualDensity.compact,
              ),
              icon: Icon(copied ? Icons.check : Icons.link, size: 17),
              label: Text(copied ? 'Copied' : 'Copy'),
            ),
          ],
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 18),
          child: Divider(color: Color(0xFF2B3552), height: 1),
        ),
        const Row(
          children: [
            _StepNumber(2),
            SizedBox(width: 11),
            Text(
              'Share it on your Story',
              style: TextStyle(
                color: PtwColors.textOnAccent,
                fontSize: 18,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        SizedBox(
          width: double.infinity,
          height: 60,
          child: DecoratedBox(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [PtwColors.hotPink, PtwColors.flame, PtwColors.amber],
              ),
              borderRadius: BorderRadius.all(Radius.circular(999)),
            ),
            child: FilledButton.icon(
              key: const ValueKey(ComponentIds.sharePrimary),
              onPressed: busy ? null : onShare,
              style: FilledButton.styleFrom(
                backgroundColor: PtwColors.transparent,
                disabledBackgroundColor: PtwColors.transparent,
                foregroundColor: PtwColors.textOnAccent,
                shape: const StadiumBorder(),
              ),
              icon:
                  busy
                      ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: PtwColors.textOnAccent,
                        ),
                      )
                      : const Icon(Icons.camera_alt_outlined),
              label: Text(
                busy ? 'Getting ready…' : 'Share Story',
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

final class _StepNumber extends StatelessWidget {
  const _StepNumber(this.number);

  final int number;

  @override
  Widget build(BuildContext context) => CircleAvatar(
    radius: 15,
    backgroundColor: PtwColors.textOnAccent,
    child: Text(
      '$number',
      style: const TextStyle(color: PtwColors.ink, fontWeight: FontWeight.w900),
    ),
  );
}
