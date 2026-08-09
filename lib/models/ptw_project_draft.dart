import 'ptw_image_ref.dart';
import 'ptw_project.dart';
import 'ptw_story_composition.dart';

enum PtwProjectDraftIntent { firstProject, newChallenge }

final class PtwProjectDraft {
  const PtwProjectDraft({
    required this.id,
    required this.intent,
    required this.goal,
    required this.image,
    required this.primaryColor,
    required this.createdAt,
    required this.updatedAt,
    this.doubt,
    this.deadline,
    this.previewGeneratedAt,
    this.storyComposition,
    this.category,
    this.categoryConfirmed = false,
    this.progressMetric,
  });

  factory PtwProjectDraft.fromJson(
    Map<String, dynamic> json, {
    bool migrateStoryComposition = false,
  }) => PtwProjectDraft(
    id: json['id'] as String,
    intent: PtwProjectDraftIntent.values.byName(json['intent'] as String),
    goal: json['goal'] as String? ?? '',
    doubt: json['doubt'] as String?,
    deadline:
        json['deadline'] == null
            ? null
            : DateTime.parse(json['deadline'] as String),
    image: PtwImageRef.fromJson(json['image'] as Map<String, dynamic>),
    primaryColor: json['primaryColor'] as int,
    createdAt: DateTime.parse(json['createdAt'] as String),
    updatedAt: DateTime.parse(json['updatedAt'] as String),
    previewGeneratedAt:
        json['previewGeneratedAt'] == null
            ? null
            : DateTime.parse(json['previewGeneratedAt'] as String),
    storyComposition:
        json['storyComposition'] == null
            ? null
            : PtwStoryComposition.fromJson(
              json['storyComposition'] as Map<String, dynamic>,
              migrateGeneratedValue: migrateStoryComposition,
            ),
    category:
        json['category'] == null
            ? null
            : PtwProjectCategory.values.byName(json['category'] as String),
    categoryConfirmed: json['categoryConfirmed'] as bool? ?? false,
    progressMetric:
        json['progressMetric'] == null
            ? null
            : PtwProgressMetric.fromJson(
              json['progressMetric'] as Map<String, dynamic>,
            ),
  );

  final String id;
  final PtwProjectDraftIntent intent;
  final String goal;
  final String? doubt;
  final DateTime? deadline;
  final PtwImageRef image;
  final int primaryColor;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? previewGeneratedAt;
  final PtwStoryComposition? storyComposition;
  final PtwProjectCategory? category;
  final bool categoryConfirmed;
  final PtwProgressMetric? progressMetric;

  bool get hasValidGoal => goal.trim().isNotEmpty && goal.trim().length <= 90;
  bool get hasPreview => hasValidGoal && previewGeneratedAt != null;

  PtwProjectDraft copyWith({
    String? goal,
    String? doubt,
    bool clearDoubt = false,
    DateTime? deadline,
    bool clearDeadline = false,
    PtwImageRef? image,
    int? primaryColor,
    DateTime? updatedAt,
    DateTime? previewGeneratedAt,
    bool clearPreview = false,
    PtwStoryComposition? storyComposition,
    bool clearStoryComposition = false,
    PtwProjectCategory? category,
    bool? categoryConfirmed,
    PtwProgressMetric? progressMetric,
    bool clearProgressMetric = false,
  }) => PtwProjectDraft(
    id: id,
    intent: intent,
    goal: goal ?? this.goal,
    doubt: clearDoubt ? null : doubt ?? this.doubt,
    deadline: clearDeadline ? null : deadline ?? this.deadline,
    image: image ?? this.image,
    primaryColor: primaryColor ?? this.primaryColor,
    createdAt: createdAt,
    updatedAt: updatedAt ?? this.updatedAt,
    previewGeneratedAt:
        clearPreview ? null : previewGeneratedAt ?? this.previewGeneratedAt,
    storyComposition:
        clearStoryComposition
            ? null
            : storyComposition ?? this.storyComposition,
    category: category ?? this.category,
    categoryConfirmed: categoryConfirmed ?? this.categoryConfirmed,
    progressMetric:
        clearProgressMetric ? null : progressMetric ?? this.progressMetric,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'intent': intent.name,
    'goal': goal,
    'doubt': doubt,
    'deadline': deadline?.toIso8601String(),
    'image': image.toJson(),
    'primaryColor': primaryColor,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
    'previewGeneratedAt': previewGeneratedAt?.toIso8601String(),
    'storyComposition': storyComposition?.toJson(),
    'category': category?.name,
    'categoryConfirmed': categoryConfirmed,
    'progressMetric': progressMetric?.toJson(),
  };
}
