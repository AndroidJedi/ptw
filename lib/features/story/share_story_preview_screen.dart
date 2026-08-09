import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/data/ptw_media_service.dart';
import '../../core/theme/ptw_colors.dart';
import '../../features/share/share_models.dart';
import '../../features/share/share_service.dart';
import '../../generated_share_editor/generated_share_editor.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_share_record.dart';
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
  ShareEditorController? _controller;
  ShareEditorContent? _content;
  PtwStoryComposition? _baseComposition;
  PtwAppState? _appState;
  PtwProject? _subject;
  Timer? _autosaveTimer;
  String? _activatedProjectId;
  bool _copied = false;
  bool _busy = false;
  bool _showShareStep = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = PtwScope.of(context);
    _appState = state;
    _controller ??= _createController(state);
  }

  ShareEditorController? _createController(PtwAppState state) {
    final project = _storyProject(state);
    if (project == null) return null;
    _subject = project;
    var event = widget.event ?? ShareEvent.manual;
    var momentId = widget.momentId;
    if (!widget.isDraft && widget.source == PtwShareSource.launch) {
      final recommendation = state.recommendedShareFor(project.id);
      event = recommendation.event;
      momentId = recommendation.momentId;
    }
    final saved = state.draft?.storyComposition;
    final composition =
        widget.isDraft && saved?.projectId == project.id
            ? saved!
            : _adapter.createBase(
              project: project,
              event: event,
              momentId: momentId,
              now: state.now,
            );
    _baseComposition = composition;
    final content = _adapter.content(
      project: project,
      composition: composition,
    );
    _content = content;
    final controller = ShareEditorController(
      theme: state.shareEditorTheme,
      content: content,
      mode: ShareEditorMode.runtime,
      initialValue: _adapter.value(
        theme: state.shareEditorTheme,
        content: content,
        composition: composition,
      ),
    )..addListener(_onCompositionChanged);
    if (widget.isDraft && saved == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final current = _currentComposition;
        if (mounted && current != null) {
          unawaited(state.saveDraftStory(current));
        }
      });
    }
    return controller;
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
    );
  }

  void _onCompositionChanged() {
    if (!mounted) return;
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
      if (!mounted) {
        return const InstagramGuideShareResult(
          InstagramGuideShareStatus.failed,
        );
      }
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
    if (composition == null ||
        composition.headline.trim().isEmpty ||
        composition.dare.trim().isEmpty) {
      _message('Both Story lines are required.');
      return;
    }
    await _persistDraftNow();
    if (!mounted) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => _showShareStep = true);
  }

  void _backToBuilder() {
    if (_busy) return;
    setState(() => _showShareStep = false);
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    final state = _appState;
    final content = _content;
    if (controller == null || state == null || content == null) {
      return const Scaffold(
        body: Center(child: Text('This Story is no longer available.')),
      );
    }
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        if (_showShareStep) {
          _backToBuilder();
        } else {
          unawaited(_close());
        }
      },
      child: Scaffold(
        key: const ValueKey(ComponentIds.shareScreen),
        backgroundColor: const Color(0xFF0E1423),
        body: SafeArea(
          child:
              _showShareStep
                  ? _ShareHandoff(
                    controller: controller,
                    theme: state.shareEditorTheme,
                    content: content,
                    composition: _currentComposition!,
                    imageResolver: _resolveImage,
                    copied: _copied,
                    busy: _busy,
                    onBack: _backToBuilder,
                    onCopy: _copyPressed,
                    onShare: _startShare,
                  )
                  : GeneratedShareEditor(
                    theme: state.shareEditorTheme,
                    content: content,
                    controller: controller,
                    imagePicker: _pickEditorImage,
                    imageResolver: _resolveImage,
                    onClose: () => unawaited(_close()),
                    onContinue: () => unawaited(_openShareStep()),
                    onLockedFeatureTap:
                        (feature) => _message(
                          '${feature.label} requires premium access.',
                        ),
                  ),
        ),
      ),
    );
  }
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
