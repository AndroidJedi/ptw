import 'ptw_image_ref.dart';

/// Lightweight proof published while a project is in progress.
final class PtwEvidence {
  const PtwEvidence({
    required this.id,
    required this.projectId,
    required this.title,
    required this.details,
    required this.createdAt,
    this.media,
  });

  factory PtwEvidence.fromJson(Map<String, dynamic> json) => PtwEvidence(
    id: json['id'] as String,
    projectId: json['projectId'] as String,
    title: json['title'] as String,
    details: json['details'] as String,
    createdAt: DateTime.parse(json['createdAt'] as String),
    media:
        json['media'] == null
            ? null
            : PtwImageRef.fromJson(json['media'] as Map<String, dynamic>),
  );

  final String id;
  final String projectId;
  final String title;
  final String details;
  final DateTime createdAt;
  final PtwImageRef? media;

  Map<String, dynamic> toJson() => {
    'id': id,
    'projectId': projectId,
    'title': title,
    'details': details,
    'createdAt': createdAt.toIso8601String(),
    'media': media?.toJson(),
  };
}
