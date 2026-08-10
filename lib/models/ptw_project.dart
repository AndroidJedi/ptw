import 'ptw_image_ref.dart';

enum PtwProjectStatus { active, completed }

enum PtwProjectCategory {
  startup,
  business,
  career,
  fitness,
  creative,
  education,
  relationships,
  travel,
  personal,
  technology,
  other;

  String get label => switch (this) {
    startup => 'Startup',
    business => 'Business',
    career => 'Career',
    fitness => 'Fitness',
    creative => 'Creative',
    education => 'Education',
    relationships => 'Relationships',
    travel => 'Travel',
    personal => 'Personal',
    technology => 'Technology',
    other => 'Other',
  };
}

/// A small, deterministic classifier used to suggest a semantic asset pack.
final class PtwProjectCategorySuggester {
  const PtwProjectCategorySuggester();

  PtwProjectCategory suggest(String goal) {
    final normalized = goal.toLowerCase().replaceAll(
      RegExp(r'[^a-z0-9\s]+'),
      ' ',
    );
    final scores = <PtwProjectCategory, int>{};
    for (final entry in _keywords.entries) {
      var score = 0;
      for (final keyword in entry.value) {
        if (RegExp(
          '(?:^|\\s)${RegExp.escape(keyword)}(?:\\s|\$)',
        ).hasMatch(normalized)) {
          score += keyword.contains(' ') ? 3 : 1;
        }
      }
      scores[entry.key] = score;
    }
    final best = scores.values.fold<int>(
      0,
      (value, item) => item > value ? item : value,
    );
    if (best == 0) return PtwProjectCategory.other;
    final winners = scores.entries.where((entry) => entry.value == best);
    return winners.length == 1 ? winners.single.key : PtwProjectCategory.other;
  }

  static const _keywords = <PtwProjectCategory, List<String>>{
    PtwProjectCategory.startup: [
      'startup',
      'founder',
      'launch',
      'mvp',
      'customers',
      'users',
      'product',
    ],
    PtwProjectCategory.business: [
      'business',
      'revenue',
      'sales',
      'client',
      'clients',
      'profit',
      'company',
    ],
    PtwProjectCategory.career: [
      'career',
      'job',
      'promotion',
      'interview',
      'portfolio',
      'resume',
      'work',
    ],
    PtwProjectCategory.fitness: [
      'fitness',
      'gym',
      'run',
      'running',
      'workout',
      'weight',
      'marathon',
      'train',
    ],
    PtwProjectCategory.creative: [
      'creative',
      'write',
      'book',
      'paint',
      'music',
      'film',
      'design',
      'art',
    ],
    PtwProjectCategory.education: [
      'learn',
      'study',
      'course',
      'school',
      'exam',
      'degree',
      'language',
      'education',
    ],
    PtwProjectCategory.relationships: [
      'relationship',
      'family',
      'partner',
      'friends',
      'community',
      'dating',
      'marriage',
    ],
    PtwProjectCategory.travel: [
      'travel',
      'trip',
      'country',
      'countries',
      'flight',
      'hike',
      'adventure',
    ],
    PtwProjectCategory.personal: [
      'habit',
      'routine',
      'confidence',
      'mindset',
      'personal',
      'journal',
      'sleep',
    ],
    PtwProjectCategory.technology: [
      'technology',
      'tech',
      'code',
      'coding',
      'app',
      'software',
      'ai',
      'developer',
    ],
  };
}

final class PtwProgressMetric {
  const PtwProgressMetric({
    required this.start,
    required this.current,
    required this.target,
    required this.unit,
  }) : assert(start != target),
       assert(unit != '');

  factory PtwProgressMetric.fromJson(Map<String, dynamic> json) {
    final start = (json['start'] as num).toDouble();
    final current = (json['current'] as num).toDouble();
    final target = (json['target'] as num).toDouble();
    final unit = (json['unit'] as String).trim();
    if (start == target || unit.isEmpty) {
      throw const FormatException('Invalid project progress metric');
    }
    return PtwProgressMetric(
      start: start,
      current: current,
      target: target,
      unit: unit,
    );
  }

  final double start;
  final double current;
  final double target;
  final String unit;

  double get fraction => ((current - start) / (target - start)).clamp(0, 1);
  int get percentage => (fraction * 100).round();

  String get currentLabel => '${_compactNumber(current)} $unit'.trim();
  String get progressLabel => '$percentage%';

  PtwProgressMetric copyWith({double? current}) => PtwProgressMetric(
    start: start,
    current: current ?? this.current,
    target: target,
    unit: unit,
  );

  Map<String, dynamic> toJson() => {
    'start': start,
    'current': current,
    'target': target,
    'unit': unit,
  };

  static String _compactNumber(double value) =>
      value == value.roundToDouble()
          ? value.toInt().toString()
          : value.toStringAsFixed(1);
}

/// The single image-led public goal used throughout the redesigned prototype.
final class PtwProject {
  const PtwProject({
    required this.id,
    required this.ownerId,
    required this.ownerName,
    required this.ownerHandle,
    required this.ownerAvatarAsset,
    required this.goal,
    this.doubt,
    this.deadline,
    required this.image,
    required this.primaryColor,
    required this.status,
    required this.createdAt,
    this.category,
    this.categoryConfirmed = false,
    this.progressMetric,
  });

  factory PtwProject.fromJson(Map<String, dynamic> json) => PtwProject(
    id: json['id'] as String,
    ownerId: json['ownerId'] as String,
    ownerName: json['ownerName'] as String,
    ownerHandle: json['ownerHandle'] as String,
    ownerAvatarAsset: json['ownerAvatarAsset'] as String,
    goal: json['goal'] as String,
    doubt: json['doubt'] as String?,
    deadline:
        json['deadline'] == null
            ? null
            : DateTime.parse(json['deadline'] as String),
    image: PtwImageRef.fromJson(json['image'] as Map<String, dynamic>),
    primaryColor: json['primaryColor'] as int,
    status: PtwProjectStatus.values.byName(json['status'] as String),
    createdAt: DateTime.parse(json['createdAt'] as String),
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
  final String ownerId;
  final String ownerName;
  final String ownerHandle;
  final String ownerAvatarAsset;
  final String goal;
  final String? doubt;
  final DateTime? deadline;
  final PtwImageRef image;
  final int primaryColor;
  final PtwProjectStatus status;
  final DateTime createdAt;
  final PtwProjectCategory? category;
  final bool categoryConfirmed;
  final PtwProgressMetric? progressMetric;

  PtwProject copyWith({
    String? goal,
    PtwProjectCategory? category,
    bool? categoryConfirmed,
    PtwProgressMetric? progressMetric,
    bool clearProgressMetric = false,
    PtwProjectStatus? status,
  }) => PtwProject(
    id: id,
    ownerId: ownerId,
    ownerName: ownerName,
    ownerHandle: ownerHandle,
    ownerAvatarAsset: ownerAvatarAsset,
    goal: goal ?? this.goal,
    doubt: doubt,
    deadline: deadline,
    image: image,
    primaryColor: primaryColor,
    status: status ?? this.status,
    createdAt: createdAt,
    category: category ?? this.category,
    categoryConfirmed: categoryConfirmed ?? this.categoryConfirmed,
    progressMetric:
        clearProgressMetric ? null : progressMetric ?? this.progressMetric,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'ownerId': ownerId,
    'ownerName': ownerName,
    'ownerHandle': ownerHandle,
    'ownerAvatarAsset': ownerAvatarAsset,
    'goal': goal,
    'doubt': doubt,
    'deadline': deadline?.toIso8601String(),
    'image': image.toJson(),
    'primaryColor': primaryColor,
    'status': status.name,
    'createdAt': createdAt.toIso8601String(),
    'category': category?.name,
    'categoryConfirmed': categoryConfirmed,
    'progressMetric': progressMetric?.toJson(),
  };
}
