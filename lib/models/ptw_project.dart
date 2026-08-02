import 'ptw_image_ref.dart';

enum PtwProjectStatus { active, completed }

/// The single image-led public goal used throughout the redesigned prototype.
final class PtwProject {
  const PtwProject({
    required this.id,
    required this.ownerId,
    required this.ownerName,
    required this.ownerHandle,
    required this.ownerAvatarAsset,
    required this.goal,
    required this.deadline,
    required this.image,
    required this.primaryColor,
    required this.status,
    required this.createdAt,
  });

  factory PtwProject.fromJson(Map<String, dynamic> json) => PtwProject(
    id: json['id'] as String,
    ownerId: json['ownerId'] as String,
    ownerName: json['ownerName'] as String,
    ownerHandle: json['ownerHandle'] as String,
    ownerAvatarAsset: json['ownerAvatarAsset'] as String,
    goal: json['goal'] as String,
    deadline: DateTime.parse(json['deadline'] as String),
    image: PtwImageRef.fromJson(json['image'] as Map<String, dynamic>),
    primaryColor: json['primaryColor'] as int,
    status: PtwProjectStatus.values.byName(json['status'] as String),
    createdAt: DateTime.parse(json['createdAt'] as String),
  );

  final String id;
  final String ownerId;
  final String ownerName;
  final String ownerHandle;
  final String ownerAvatarAsset;
  final String goal;
  final DateTime deadline;
  final PtwImageRef image;
  final int primaryColor;
  final PtwProjectStatus status;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
    'id': id,
    'ownerId': ownerId,
    'ownerName': ownerName,
    'ownerHandle': ownerHandle,
    'ownerAvatarAsset': ownerAvatarAsset,
    'goal': goal,
    'deadline': deadline.toIso8601String(),
    'image': image.toJson(),
    'primaryColor': primaryColor,
    'status': status.name,
    'createdAt': createdAt.toIso8601String(),
  };
}
