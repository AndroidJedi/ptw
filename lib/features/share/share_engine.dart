import '../../models/ptw_evidence.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_response.dart';
import 'share_models.dart';

final class ShareStatisticsFormatter {
  const ShareStatisticsFormatter();

  String compact(int value) {
    if (value < 1000) return '$value';
    if (value < 1000000) {
      final scaled = value / 1000;
      return '${scaled.toStringAsFixed(scaled >= 10 ? 0 : 1)}K';
    }
    final scaled = value / 1000000;
    return '${scaled.toStringAsFixed(scaled >= 10 ? 0 : 1)}M';
  }

  int percentage(int part, int total) {
    if (total <= 0) return 0;
    return ((part / total) * 100).round().clamp(0, 100);
  }
}

final class ShareCopyGenerator {
  const ShareCopyGenerator();

  String captionWithLink(ShareCardData data) =>
      '${data.caption.trim()}\n\n${data.publicLink}';
}

final class ShareCardBuilder {
  const ShareCardBuilder({
    this.statisticsFormatter = const ShareStatisticsFormatter(),
  });

  final ShareStatisticsFormatter statisticsFormatter;

  ShareCardData build({
    required ShareCatalog catalog,
    required PtwProject project,
    required List<PtwResponse> responses,
    required List<PtwEvidence> evidence,
    required ShareTemplateType template,
    required ShareEvent event,
    required int variationIndex,
    required DateTime referenceTime,
  }) {
    final definition = catalog.template(template);
    final resolvedVariationIndex =
        variationIndex % definition.variations.length;
    final variation = definition.variations[resolvedVariationIndex];
    final fallback = definition.fallback;
    final doubts = responses
        .where((item) => item.side == PtwResponseSide.doubt)
        .toList(growable: false);
    final supporters =
        responses.where((item) => item.side == PtwResponseSide.believe).length;
    final skeptics = doubts.length;
    final latestProof = evidence.isEmpty ? null : evidence.first;
    final dayNumber = referenceTime.difference(project.createdAt).inDays + 1;
    final totalResponses = supporters + skeptics;

    var usesFallback = false;
    var featuredComment = doubts.firstOrNull?.message ?? '';
    var authorResponse = _fallbackString(fallback, 'authorResponse');
    var progressValue = statisticsFormatter.compact(totalResponses);
    var progressMetric = 'people responded';
    var progressSecondary =
        '${evidence.length} ${evidence.length == 1 ? 'proof' : 'proofs'} posted';
    var milestone = latestProof?.title ?? '';
    var resultLead = '${dayNumber.clamp(1, 999)} days of public progress';
    var resultOutcome = 'Goal completed.';
    var doubtPercent = statisticsFormatter.percentage(skeptics, totalResponses);
    var opinionChange = _fallbackString(fallback, 'opinionChange');

    switch (template) {
      case ShareTemplateType.challenge:
        break;
      case ShareTemplateType.criticism:
        if (featuredComment.isEmpty) {
          featuredComment = _fallbackString(fallback, 'featuredComment');
          usesFallback = true;
        }
        break;
      case ShareTemplateType.progress:
        if (totalResponses == 0 && evidence.isEmpty) {
          progressValue = _fallbackString(fallback, 'progressValue');
          progressMetric = _fallbackString(fallback, 'progressMetric');
          progressSecondary = _fallbackString(fallback, 'progressSecondary');
          usesFallback = true;
        }
        break;
      case ShareTemplateType.milestone:
        if (milestone.isEmpty) {
          milestone = _fallbackString(fallback, 'milestone');
          progressSecondary = _fallbackString(fallback, 'progressSecondary');
          usesFallback = true;
        } else {
          progressSecondary = latestProof!.details;
        }
        break;
      case ShareTemplateType.result:
        if (project.status != PtwProjectStatus.completed) {
          resultLead = _fallbackString(fallback, 'resultLead');
          resultOutcome = _fallbackString(fallback, 'resultOutcome');
          doubtPercent = _fallbackInt(fallback, 'doubtPercent');
          usesFallback = true;
        }
        break;
      case ShareTemplateType.opinionChange:
        featuredComment = _fallbackString(fallback, 'featuredComment');
        opinionChange = _fallbackString(fallback, 'opinionChange');
        usesFallback = true;
        break;
    }

    return ShareCardData(
      projectId: project.id,
      template: template,
      event: event,
      ownerName: project.ownerName,
      ownerHandle: project.ownerHandle,
      ownerAvatarAsset: project.ownerAvatarAsset,
      background: latestProof?.media ?? project.image,
      challengeTitle: project.goal,
      deadline: project.deadline,
      primaryColor: project.primaryColor,
      hook: variation.hook,
      caption: variation.caption,
      cta: variation.cta,
      gradientVariant: variation.gradientVariant,
      supporterCount: supporters,
      skepticCount: skeptics,
      commentCount: totalResponses,
      dayNumber: dayNumber.clamp(1, 999),
      progressValue: progressValue,
      progressMetric: progressMetric,
      progressSecondary: progressSecondary,
      featuredComment: featuredComment,
      authorResponse: authorResponse,
      milestone: milestone,
      resultLead: resultLead,
      resultOutcome: resultOutcome,
      doubtPercent: doubtPercent,
      opinionChange: opinionChange,
      usesFallbackData: usesFallback,
      variationIndex: resolvedVariationIndex,
    );
  }

  static String _fallbackString(Map<String, dynamic> fallback, String key) {
    final value = fallback[key];
    if (value is! String || value.trim().isEmpty) return '';
    return value;
  }

  static int _fallbackInt(Map<String, dynamic> fallback, String key) =>
      fallback[key] as int? ?? 0;
}

final class ShareEngine {
  const ShareEngine({
    required this.catalog,
    this.cardBuilder = const ShareCardBuilder(),
    this.copyGenerator = const ShareCopyGenerator(),
    this.statisticsFormatter = const ShareStatisticsFormatter(),
  });

  final ShareCatalog catalog;
  final ShareCardBuilder cardBuilder;
  final ShareCopyGenerator copyGenerator;
  final ShareStatisticsFormatter statisticsFormatter;

  ShareCardData buildCard({
    required PtwProject project,
    required List<PtwResponse> responses,
    required List<PtwEvidence> evidence,
    required ShareTemplateType template,
    required ShareEvent event,
    required int variationIndex,
    required DateTime referenceTime,
  }) => cardBuilder.build(
    catalog: catalog,
    project: project,
    responses: responses,
    evidence: evidence,
    template: template,
    event: event,
    variationIndex: variationIndex,
    referenceTime: referenceTime,
  );
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
