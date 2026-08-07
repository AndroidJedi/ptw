import 'dart:typed_data';

import '../../models/ptw_image_ref.dart';

enum ShareTemplateType {
  challenge,
  criticism,
  progress,
  milestone,
  result,
  opinionChange;

  static ShareTemplateType fromWire(String value) {
    try {
      return ShareTemplateType.values.byName(value);
    } on ArgumentError {
      throw FormatException('Unknown share template: $value');
    }
  }

  String get label => switch (this) {
    challenge => 'Challenge',
    criticism => 'Criticism',
    progress => 'Progress',
    milestone => 'Milestone',
    result => 'Result',
    opinionChange => 'Mind changed',
  };
}

enum ShareFormat {
  story(width: 1080, height: 1920, label: 'Story', ratioLabel: '9:16'),
  square(width: 1080, height: 1080, label: 'Square', ratioLabel: '1:1'),
  portrait(width: 1080, height: 1350, label: 'Portrait', ratioLabel: '4:5');

  const ShareFormat({
    required this.width,
    required this.height,
    required this.label,
    required this.ratioLabel,
  });

  final int width;
  final int height;
  final String label;
  final String ratioLabel;

  double get aspectRatio => width / height;
}

enum ShareEvent {
  manual,
  challengeCreated,
  firstComment,
  topCommentChanged,
  milestoneReached,
  weeklyProgress,
  newSupporter,
  newSkeptic,
  opinionChanged,
  goalCompleted;

  static ShareEvent fromWire(String? value) {
    if (value == null) return ShareEvent.manual;
    return ShareEvent.values.where((item) => item.name == value).firstOrNull ??
        ShareEvent.manual;
  }

  ShareTemplateType get recommendedTemplate => switch (this) {
    challengeCreated => ShareTemplateType.challenge,
    firstComment ||
    topCommentChanged ||
    newSkeptic => ShareTemplateType.criticism,
    milestoneReached => ShareTemplateType.milestone,
    weeklyProgress || newSupporter => ShareTemplateType.progress,
    opinionChanged => ShareTemplateType.opinionChange,
    goalCompleted => ShareTemplateType.result,
    manual => ShareTemplateType.challenge,
  };
}

final class ShareCopyVariation {
  const ShareCopyVariation({
    required this.hook,
    required this.caption,
    required this.cta,
    required this.gradientVariant,
  });

  factory ShareCopyVariation.fromJson(Map<String, dynamic> json) =>
      ShareCopyVariation(
        hook: _requiredString(json, 'hook'),
        caption: _requiredString(json, 'caption'),
        cta: _requiredString(json, 'cta'),
        gradientVariant: json['gradientVariant'] as int? ?? 0,
      );

  final String hook;
  final String caption;
  final String cta;
  final int gradientVariant;
}

final class ShareTemplateDefinition {
  const ShareTemplateDefinition({
    required this.type,
    required this.fallback,
    required this.variations,
  });

  factory ShareTemplateDefinition.fromJson(Map<String, dynamic> json) {
    final type = ShareTemplateType.fromWire(_requiredString(json, 'type'));
    final fallback = Map<String, dynamic>.unmodifiable(
      _requiredObject(json['fallback']),
    );
    _validateFallback(type, fallback);
    final variations = _requiredList(json, 'variations')
        .map(_requiredObject)
        .map(ShareCopyVariation.fromJson)
        .toList(growable: false);
    if (variations.isEmpty) {
      throw const FormatException('Share template needs a variation');
    }
    return ShareTemplateDefinition(
      type: type,
      fallback: fallback,
      variations: List.unmodifiable(variations),
    );
  }

  final ShareTemplateType type;
  final Map<String, dynamic> fallback;
  final List<ShareCopyVariation> variations;

  static void _validateFallback(
    ShareTemplateType type,
    Map<String, dynamic> fallback,
  ) {
    void string(String key) {
      final value = fallback[key];
      if (value is! String || value.trim().isEmpty) {
        throw FormatException('${type.name} fallback requires $key');
      }
    }

    void integer(String key) {
      if (fallback[key] is! int) {
        throw FormatException('${type.name} fallback requires $key');
      }
    }

    switch (type) {
      case ShareTemplateType.challenge:
        break;
      case ShareTemplateType.criticism:
        string('featuredComment');
        string('authorResponse');
        break;
      case ShareTemplateType.progress:
        integer('dayNumber');
        string('progressValue');
        string('progressMetric');
        string('progressSecondary');
        break;
      case ShareTemplateType.milestone:
        string('milestone');
        string('progressSecondary');
        break;
      case ShareTemplateType.result:
        string('resultLead');
        string('resultOutcome');
        integer('doubtPercent');
        break;
      case ShareTemplateType.opinionChange:
        string('featuredComment');
        string('opinionChange');
        break;
    }
  }
}

final class ShareCatalog {
  const ShareCatalog({required this.templates, required this.scenarios});

  factory ShareCatalog.fromJson(Map<String, dynamic> json) {
    final definitions = _requiredList(json, 'templates')
        .map(_requiredObject)
        .map(ShareTemplateDefinition.fromJson)
        .toList(growable: false);
    final scenarios = _requiredList(
      json,
      'scenarios',
    ).map(_requiredObject).map(ShareCardData.fromJson).toList(growable: false);
    final templates = {
      for (final definition in definitions) definition.type: definition,
    };
    if (templates.length != ShareTemplateType.values.length) {
      throw const FormatException(
        'Share catalog must define every template exactly once',
      );
    }
    if (scenarios.map((item) => item.template).toSet().length !=
        ShareTemplateType.values.length) {
      throw const FormatException(
        'Share catalog must include a JSON scenario for every template',
      );
    }
    return ShareCatalog(
      templates: Map.unmodifiable(templates),
      scenarios: List.unmodifiable(scenarios),
    );
  }

  final Map<ShareTemplateType, ShareTemplateDefinition> templates;
  final List<ShareCardData> scenarios;

  ShareTemplateDefinition template(ShareTemplateType type) => templates[type]!;
}

final class ShareCardData {
  const ShareCardData({
    required this.projectId,
    required this.template,
    required this.event,
    required this.ownerName,
    required this.ownerHandle,
    required this.ownerAvatarAsset,
    required this.background,
    required this.challengeTitle,
    required this.deadline,
    required this.primaryColor,
    required this.hook,
    required this.caption,
    required this.cta,
    required this.gradientVariant,
    required this.supporterCount,
    required this.skepticCount,
    required this.commentCount,
    required this.dayNumber,
    required this.progressValue,
    required this.progressMetric,
    required this.progressSecondary,
    required this.featuredComment,
    required this.authorResponse,
    required this.milestone,
    required this.resultLead,
    required this.resultOutcome,
    required this.doubtPercent,
    required this.opinionChange,
    required this.usesFallbackData,
    required this.variationIndex,
  });

  factory ShareCardData.fromJson(Map<String, dynamic> json) => ShareCardData(
    projectId: _requiredString(json, 'projectId'),
    template: ShareTemplateType.fromWire(_requiredString(json, 'template')),
    event: ShareEvent.fromWire(json['event'] as String?),
    ownerName: _requiredString(json, 'ownerName'),
    ownerHandle: _requiredString(json, 'ownerHandle'),
    ownerAvatarAsset: _requiredString(json, 'ownerAvatarAsset'),
    background: PtwImageRef.fromJson(_requiredObject(json['background'])),
    challengeTitle: _requiredString(json, 'challengeTitle'),
    deadline:
        json['deadline'] == null
            ? null
            : DateTime.parse(json['deadline'] as String),
    primaryColor: _requiredInt(json, 'primaryColor'),
    hook: _requiredString(json, 'hook'),
    caption: _requiredString(json, 'caption'),
    cta: _requiredString(json, 'cta'),
    gradientVariant: _requiredInt(json, 'gradientVariant'),
    supporterCount: _requiredInt(json, 'supporterCount'),
    skepticCount: _requiredInt(json, 'skepticCount'),
    commentCount: _requiredInt(json, 'commentCount'),
    dayNumber: _requiredInt(json, 'dayNumber'),
    progressValue: _requiredString(json, 'progressValue'),
    progressMetric: _requiredString(json, 'progressMetric'),
    progressSecondary: _requiredString(json, 'progressSecondary'),
    featuredComment: _string(json, 'featuredComment'),
    authorResponse: _string(json, 'authorResponse'),
    milestone: _string(json, 'milestone'),
    resultLead: _requiredString(json, 'resultLead'),
    resultOutcome: _requiredString(json, 'resultOutcome'),
    doubtPercent: _requiredInt(json, 'doubtPercent'),
    opinionChange: _string(json, 'opinionChange'),
    usesFallbackData: _requiredBool(json, 'usesFallbackData'),
    variationIndex: _requiredInt(json, 'variationIndex'),
  );

  final String projectId;
  final ShareTemplateType template;
  final ShareEvent event;
  final String ownerName;
  final String ownerHandle;
  final String ownerAvatarAsset;
  final PtwImageRef background;
  final String challengeTitle;
  final DateTime? deadline;
  final int primaryColor;
  final String hook;
  final String caption;
  final String cta;
  final int gradientVariant;
  final int supporterCount;
  final int skepticCount;
  final int commentCount;
  final int dayNumber;
  final String progressValue;
  final String progressMetric;
  final String progressSecondary;
  final String featuredComment;
  final String authorResponse;
  final String milestone;
  final String resultLead;
  final String resultOutcome;
  final int doubtPercent;
  final String opinionChange;
  final bool usesFallbackData;
  final int variationIndex;

  String get publicLink => 'https://ptw.to/p/$projectId';

  Map<String, dynamic> toJson() => {
    'projectId': projectId,
    'template': template.name,
    'event': event.name,
    'ownerName': ownerName,
    'ownerHandle': ownerHandle,
    'ownerAvatarAsset': ownerAvatarAsset,
    'background': background.toJson(),
    'challengeTitle': challengeTitle,
    'deadline': deadline?.toIso8601String(),
    'primaryColor': primaryColor,
    'hook': hook,
    'caption': caption,
    'cta': cta,
    'gradientVariant': gradientVariant,
    'supporterCount': supporterCount,
    'skepticCount': skepticCount,
    'commentCount': commentCount,
    'dayNumber': dayNumber,
    'progressValue': progressValue,
    'progressMetric': progressMetric,
    'progressSecondary': progressSecondary,
    'featuredComment': featuredComment,
    'authorResponse': authorResponse,
    'milestone': milestone,
    'resultLead': resultLead,
    'resultOutcome': resultOutcome,
    'doubtPercent': doubtPercent,
    'opinionChange': opinionChange,
    'usesFallbackData': usesFallbackData,
    'variationIndex': variationIndex,
  };

  ShareCardData copyWith({String? hook, String? caption}) => ShareCardData(
    projectId: projectId,
    template: template,
    event: event,
    ownerName: ownerName,
    ownerHandle: ownerHandle,
    ownerAvatarAsset: ownerAvatarAsset,
    background: background,
    challengeTitle: challengeTitle,
    deadline: deadline,
    primaryColor: primaryColor,
    hook: hook ?? this.hook,
    caption: caption ?? this.caption,
    cta: cta,
    gradientVariant: gradientVariant,
    supporterCount: supporterCount,
    skepticCount: skepticCount,
    commentCount: commentCount,
    dayNumber: dayNumber,
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
    usesFallbackData: usesFallbackData,
    variationIndex: variationIndex,
  );
}

final class ShareAsset {
  const ShareAsset({
    required this.bytes,
    required this.format,
    required this.fileName,
  });

  final Uint8List bytes;
  final ShareFormat format;
  final String fileName;

  String get mimeType => 'image/png';
}

final class ShareRecommendation {
  const ShareRecommendation({
    required this.event,
    required this.template,
    this.momentId,
  });

  final ShareEvent event;
  final ShareTemplateType template;
  final String? momentId;
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Missing non-empty string: $key');
  }
  return value;
}

String _string(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String) throw FormatException('Missing string: $key');
  return value;
}

List<dynamic> _requiredList(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! List<dynamic>) {
    throw FormatException('Missing list: $key');
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) throw FormatException('Missing integer: $key');
  return value;
}

bool _requiredBool(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! bool) throw FormatException('Missing boolean: $key');
  return value;
}

Map<String, dynamic> _requiredObject(dynamic value) {
  if (value is! Map<String, dynamic>) {
    throw const FormatException('Expected JSON object');
  }
  return value;
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
