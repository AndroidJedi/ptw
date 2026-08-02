enum PtwResponseSide { believe, doubt }

/// A private anonymous message and position submitted together.
final class PtwResponse {
  const PtwResponse({
    required this.id,
    required this.projectId,
    required this.side,
    required this.message,
    required this.createdAt,
    this.readAt,
  });

  factory PtwResponse.fromJson(Map<String, dynamic> json) => PtwResponse(
    id: json['id'] as String,
    projectId: json['projectId'] as String,
    side: PtwResponseSide.values.byName(json['side'] as String),
    message: json['message'] as String,
    createdAt: DateTime.parse(json['createdAt'] as String),
    readAt:
        json['readAt'] == null
            ? null
            : DateTime.parse(json['readAt'] as String),
  );

  final String id;
  final String projectId;
  final PtwResponseSide side;
  final String message;
  final DateTime createdAt;
  final DateTime? readAt;

  bool get isRead => readAt != null;

  PtwResponse markRead(DateTime value) => PtwResponse(
    id: id,
    projectId: projectId,
    side: side,
    message: message,
    createdAt: createdAt,
    readAt: readAt ?? value,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'projectId': projectId,
    'side': side.name,
    'message': message,
    'createdAt': createdAt.toIso8601String(),
    'readAt': readAt?.toIso8601String(),
  };
}
