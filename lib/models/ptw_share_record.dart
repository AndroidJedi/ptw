import '../features/share/share_models.dart';
import 'ptw_story_composition.dart';

enum PtwShareSource {
  onboarding,
  newChallenge,
  launch,
  project,
  evidence,
  inbox,
}

enum PtwShareOutcome { success, copied, dismissed, unavailable, failed }

final class PtwShareRecord {
  const PtwShareRecord({
    required this.id,
    required this.projectId,
    required this.source,
    required this.outcome,
    this.card,
    this.story,
    required this.format,
    required this.startedAt,
    required this.completedAt,
    this.momentId,
    this.target,
  }) : assert(card != null || story != null);

  factory PtwShareRecord.fromJson(
    Map<String, dynamic> json, {
    bool migrateStoryComposition = false,
  }) => PtwShareRecord(
    id: json['id'] as String,
    projectId: json['projectId'] as String,
    source: PtwShareSource.values.byName(json['source'] as String),
    outcome: PtwShareOutcome.values.byName(json['outcome'] as String),
    card:
        json['card'] == null
            ? null
            : ShareCardData.fromJson(json['card'] as Map<String, dynamic>),
    story:
        json['story'] == null
            ? null
            : PtwStoryComposition.fromJson(
              json['story'] as Map<String, dynamic>,
              migrateGeneratedValue: migrateStoryComposition,
            ),
    format: ShareFormat.values.byName(json['format'] as String),
    startedAt: DateTime.parse(json['startedAt'] as String),
    completedAt: DateTime.parse(json['completedAt'] as String),
    momentId: json['momentId'] as String?,
    target: json['target'] as String?,
  );

  final String id;
  final String projectId;
  final PtwShareSource source;
  final PtwShareOutcome outcome;
  final ShareCardData? card;
  final PtwStoryComposition? story;
  final ShareFormat format;
  final DateTime startedAt;
  final DateTime completedAt;
  final String? momentId;
  final String? target;

  bool get isMeaningfulShare =>
      outcome == PtwShareOutcome.success || outcome == PtwShareOutcome.copied;

  Map<String, dynamic> toJson() => {
    'id': id,
    'projectId': projectId,
    'source': source.name,
    'outcome': outcome.name,
    'card': card?.toJson(),
    'story': story?.toJson(),
    'format': format.name,
    'startedAt': startedAt.toIso8601String(),
    'completedAt': completedAt.toIso8601String(),
    'momentId': momentId,
    'target': target,
  };
}
