import '../../generated_share_editor/generated_share_editor.dart';
import '../../models/ptw_evidence.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_response.dart';
import '../../models/ptw_share_generation_event.dart';
import '../../models/ptw_share_record.dart';
import 'share_models.dart';

abstract interface class ShareGenerationEventSink {
  Future<void> recordShareGenerationEvent(ShareGenerationEvent event);
}

final class ShareGenerationContext {
  ShareGenerationContext({
    required this.theme,
    required this.project,
    required this.evidence,
    required this.responses,
    required this.previousShares,
    required this.event,
    required this.journeyState,
    required this.now,
    this.momentId,
    this.regenerationIndex = 0,
    this.stickersAllowed = false,
  });

  final ShareThemeConfig theme;
  final PtwProject project;
  final List<PtwEvidence> evidence;
  final List<PtwResponse> responses;
  final List<PtwShareRecord> previousShares;
  final ShareEvent event;
  final ShareJourneyState journeyState;
  final DateTime now;
  final String? momentId;
  final int regenerationIndex;
  final bool stickersAllowed;

  int get dayNumber =>
      now.difference(project.createdAt).inDays.clamp(0, 998) + 1;

  PtwEvidence? get latestEvidence => evidence.firstOrNull;

  PtwResponse? get latestDoubt =>
      responses.where((item) => item.side == PtwResponseSide.doubt).firstOrNull;

  PtwImageRef get currentMedia =>
      evidence.map((item) => item.media).whereType<PtwImageRef>().firstOrNull ??
      project.image;

  PtwImageRef? get previousMedia {
    final current = currentMedia;
    final candidates = <PtwImageRef>[
      for (final proof in evidence)
        if (proof.media != null) proof.media!,
      ...previousShares.map(_savedShareMedia).whereType<PtwImageRef>(),
      project.image,
    ];
    return candidates.where((item) => !_sameImage(item, current)).firstOrNull;
  }

  String get progressValue =>
      project.progressMetric?.progressLabel ?? 'DAY $dayNumber';

  String get metricValue =>
      project.progressMetric?.currentLabel ??
      '${evidence.length} ${evidence.length == 1 ? 'PROOF' : 'PROOFS'} POSTED';

  double get progressFraction =>
      project.progressMetric?.fraction ??
      (evidence.isEmpty ? 0 : (evidence.length / 10).clamp(0, 1));
}

final class ShareCandidate {
  const ShareCandidate({
    required this.id,
    required this.templateId,
    required this.lookId,
    required this.family,
    required this.journeyState,
    required this.label,
    required this.headline,
    required this.secondaryText,
    required this.progressValue,
    required this.metricValue,
    required this.previousTimeLabel,
    required this.currentTimeLabel,
    required this.currentMedia,
    required this.progressFraction,
    required this.regenerationIndex,
    required this.stickersAllowed,
    this.proofLabel,
    this.previousMedia,
  });

  final String id;
  final String templateId;
  final String lookId;
  final ShareTemplateFamily family;
  final ShareJourneyState journeyState;
  final String label;
  final String headline;
  final String secondaryText;
  final String progressValue;
  final String metricValue;
  final String? proofLabel;
  final String previousTimeLabel;
  final String currentTimeLabel;
  final PtwImageRef? previousMedia;
  final PtwImageRef currentMedia;
  final double progressFraction;
  final int regenerationIndex;
  final bool stickersAllowed;

  ShareCandidate copyWith({String? lookId, String? label}) => ShareCandidate(
    id: id,
    templateId: templateId,
    lookId: lookId ?? this.lookId,
    family: family,
    journeyState: journeyState,
    label: label ?? this.label,
    headline: headline,
    secondaryText: secondaryText,
    progressValue: progressValue,
    metricValue: metricValue,
    proofLabel: proofLabel,
    previousTimeLabel: previousTimeLabel,
    currentTimeLabel: currentTimeLabel,
    previousMedia: previousMedia,
    currentMedia: currentMedia,
    progressFraction: progressFraction,
    regenerationIndex: regenerationIndex,
    stickersAllowed: stickersAllowed,
  );
}

final class PtwJourneyRecommender {
  const PtwJourneyRecommender();

  ShareJourneyState recommend({
    required PtwProject project,
    required List<PtwEvidence> evidence,
    required List<PtwShareRecord> shares,
  }) {
    if (project.status == PtwProjectStatus.completed) {
      return ShareJourneyState.finish;
    }
    final meaningful =
        shares.where((item) => item.isMeaningfulShare).toList()
          ..sort((a, b) => b.completedAt.compareTo(a.completedAt));
    final lastShare = meaningful.firstOrNull;
    final after = lastShare?.completedAt;
    final newEvidence =
        after == null
            ? evidence
            : evidence.where((item) => item.createdAt.isAfter(after)).toList();
    final progress = project.progressMetric?.fraction ?? 0;
    final hasActivity =
        meaningful.isNotEmpty || evidence.isNotEmpty || progress > 0;
    if (!hasActivity) return ShareJourneyState.beginning;

    if (lastShare?.story?.journeyState == ShareJourneyState.failure.name &&
        (newEvidence.isNotEmpty ||
            progress > (lastShare?.story?.progressFraction ?? 0))) {
      return ShareJourneyState.recovery;
    }

    final previousProgress = lastShare?.story?.progressFraction ?? 0;
    const thresholds = [0.25, 0.5, 0.75, 1.0];
    if (thresholds.any(
      (threshold) => previousProgress < threshold && progress >= threshold,
    )) {
      return ShareJourneyState.milestone;
    }
    if (newEvidence.isNotEmpty) return ShareJourneyState.smallWin;
    return ShareJourneyState.grinding;
  }
}

final class PtwShareCandidateGenerator {
  const PtwShareCandidateGenerator();

  /// Returns the preferred candidate for a one-step share entry.
  ///
  /// Generation still produces the complete three-option set so regeneration
  /// retains the same diversity guarantees. The first pass selects the
  /// highest-ranked candidate; later passes rotate through the ranked set.
  ShareCandidate generatePreferred(ShareGenerationContext context) {
    final candidates = generate(context);
    final preferred = candidates[context.regenerationIndex % candidates.length];
    if (context.regenerationIndex == 0 &&
        context.theme.looks.any((look) => look.id == 'static_note_1')) {
      return preferred.copyWith(
        lookId: 'static_note_1',
        label: '${preferred.label.split(' · ').first} · Static Note 1',
      );
    }
    return preferred;
  }

  List<ShareCandidate> generate(ShareGenerationContext context) {
    final templates = context.theme.templates
        .where(
          (template) =>
              template.status == ShareTemplateStatus.production &&
              template.supportedJourneyStates.contains(context.journeyState) &&
              _hasRequiredData(template, context),
        )
        .toList(growable: false);
    final ranked = [...templates]
      ..sort((first, second) => _compareTemplates(first, second, context));
    if (ranked.length < 3) {
      throw StateError(
        'Journey ${context.journeyState.name} needs at least three eligible templates',
      );
    }

    final chosen = <ShareTemplateConfig>[];
    for (final template in ranked) {
      if (chosen.any((item) => item.family == template.family)) continue;
      chosen.add(template);
      if (chosen.length == 3) break;
    }
    for (final template in ranked) {
      if (chosen.length == 3) break;
      if (!chosen.contains(template)) chosen.add(template);
    }

    final looks = _runtimeLooks(context.theme);
    final seed = _stableHash(
      '${context.project.id}|${context.momentId ?? ''}|${context.journeyState.name}|${context.event.name}',
    );
    final usedSeries = <String>{};
    final candidates = <ShareCandidate>[];
    for (var index = 0; index < 3; index++) {
      final look = _nextLook(
        looks,
        seed + context.regenerationIndex * 3 + index,
        usedSeries,
      );
      usedSeries.add(_lookSeries(look.id));
      final template = chosen[index];
      candidates.add(_candidate(template, look, context, index));
    }
    return List.unmodifiable(candidates);
  }

  bool _hasRequiredData(
    ShareTemplateConfig template,
    ShareGenerationContext context,
  ) => switch (template.family) {
    ShareTemplateFamily.comparison => context.previousMedia != null,
    ShareTemplateFamily.conflict =>
      context.project.doubt?.trim().isNotEmpty == true ||
          context.latestDoubt != null,
    ShareTemplateFamily.proof => context.latestEvidence != null,
    ShareTemplateFamily.milestone =>
      context.project.progressMetric != null ||
          context.evidence.isNotEmpty ||
          context.dayNumber > 1,
    _ => true,
  };

  int _compareTemplates(
    ShareTemplateConfig first,
    ShareTemplateConfig second,
    ShareGenerationContext context,
  ) {
    int score(ShareTemplateConfig template) {
      var value =
          template.primaryJourneyState == context.journeyState ? 100 : 50;
      if (template.supportsProof && context.evidence.isNotEmpty) value += 20;
      if (_preferredFamily(context.event) == template.family) value += 24;
      final familyUseCount =
          context.previousShares
              .where((share) => share.story?.familyId == template.family.name)
              .length;
      value -= familyUseCount * 6;
      final lastFamily = context.previousShares.firstOrNull?.story?.familyId;
      if (lastFamily != template.family.name) value += 12;
      if (template.family == ShareTemplateFamily.heroPhoto) value += 4;
      return value;
    }

    final byScore = score(second).compareTo(score(first));
    return byScore == 0 ? first.id.compareTo(second.id) : byScore;
  }

  ShareCandidate _candidate(
    ShareTemplateConfig template,
    ShareLookConfig look,
    ShareGenerationContext context,
    int index,
  ) {
    final proof = context.latestEvidence;
    final doubt = context.latestDoubt?.message ?? context.project.doubt;
    final goal = context.project.goal.trim();
    final headline = switch (template.family) {
      ShareTemplateFamily.progress => '${context.progressValue}: $goal',
      ShareTemplateFamily.comparison => 'Then vs now: $goal',
      ShareTemplateFamily.documentary => 'Day ${context.dayNumber}: $goal',
      ShareTemplateFamily.conflict => 'Still proving: $goal',
      ShareTemplateFamily.milestone =>
        proof?.title ?? '${context.progressValue}: $goal',
      ShareTemplateFamily.proof => proof!.title,
      _ => goal,
    };
    final secondary = switch (template.family) {
      ShareTemplateFamily.conflict => doubt!.trim(),
      ShareTemplateFamily.proof => proof!.details.trim(),
      ShareTemplateFamily.milestone when proof != null => proof.details.trim(),
      _ when context.project.doubt?.trim().isNotEmpty == true =>
        context.project.doubt!.trim(),
      _ =>
        '${context.evidence.length} ${context.evidence.length == 1 ? 'proof' : 'proofs'} posted',
    };
    final id =
        '${context.project.id}_${context.event.name}_${context.journeyState.name}_${context.regenerationIndex}_${index + 1}';
    return ShareCandidate(
      id: id,
      templateId: template.id,
      lookId: look.id,
      family: template.family,
      journeyState: context.journeyState,
      label: '${template.label} · ${look.label}',
      headline: _truncate(headline, 90),
      secondaryText: _truncate(secondary, 48),
      progressValue: context.progressValue,
      metricValue: context.metricValue,
      proofLabel: proof?.title,
      previousTimeLabel: 'BEFORE',
      currentTimeLabel: 'NOW',
      previousMedia: context.previousMedia,
      currentMedia: context.currentMedia,
      progressFraction: context.progressFraction,
      regenerationIndex: context.regenerationIndex,
      stickersAllowed: context.stickersAllowed,
    );
  }

  List<ShareLookConfig> _runtimeLooks(ShareThemeConfig theme) {
    final preferred = theme.looks.where(
      (item) => RegExp(
        r'^(soft_focus|pixel_pop|static_note|holo_crush|peach_collage|legacy_victory)_[123]$',
      ).hasMatch(item.id),
    );
    return preferred.isEmpty ? theme.looks : preferred.toList(growable: false);
  }

  ShareLookConfig _nextLook(
    List<ShareLookConfig> looks,
    int offset,
    Set<String> usedSeries,
  ) {
    for (var step = 0; step < looks.length; step++) {
      final look = looks[(offset + step).abs() % looks.length];
      if (!usedSeries.contains(_lookSeries(look.id))) return look;
    }
    return looks[offset.abs() % looks.length];
  }

  String _lookSeries(String id) => id.replaceFirst(RegExp(r'_[123]$'), '');

  int _stableHash(String value) {
    var hash = 0x811C9DC5;
    for (final codeUnit in value.codeUnits) {
      hash ^= codeUnit;
      hash = (hash * 0x01000193) & 0x7FFFFFFF;
    }
    return hash;
  }

  ShareTemplateFamily _preferredFamily(ShareEvent event) => switch (event) {
    ShareEvent.challengeCreated ||
    ShareEvent.manual => ShareTemplateFamily.heroPhoto,
    ShareEvent.firstComment ||
    ShareEvent.topCommentChanged ||
    ShareEvent.newSkeptic => ShareTemplateFamily.conflict,
    ShareEvent.milestoneReached ||
    ShareEvent.goalCompleted => ShareTemplateFamily.milestone,
    ShareEvent.weeklyProgress ||
    ShareEvent.newSupporter => ShareTemplateFamily.progress,
    ShareEvent.opinionChanged => ShareTemplateFamily.proof,
  };
}

String _truncate(String value, int maximum) {
  final normalized = value.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (normalized.length <= maximum) return normalized;
  return '${normalized.substring(0, maximum - 1).trimRight()}…';
}

bool _sameImage(PtwImageRef first, PtwImageRef second) =>
    first.source == second.source && first.path == second.path;

PtwImageRef? _savedShareMedia(PtwShareRecord share) {
  final story = share.story;
  if (story == null) return null;
  try {
    final backgroundEdit = story.editorValue?['backgroundEdit'];
    if (backgroundEdit is Map) {
      final image = backgroundEdit['image'];
      if (image is Map) {
        final source = image['source'];
        final path = image['path'];
        if (path is String && path.trim().isNotEmpty) {
          if (source == 'file') return PtwImageRef.file(path);
          if (source == 'asset') return PtwImageRef.asset(path);
        }
      }
    }
  } on Object {
    // Malformed legacy editor metadata cannot become comparison proof.
  }
  return story.projectBackground;
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
