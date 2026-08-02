/// A seeded prototype participant.
final class PtwUser {
  const PtwUser({
    required this.id,
    required this.name,
    required this.handle,
    required this.avatarAsset,
    required this.initialProjectId,
  });

  factory PtwUser.fromJson(Map<String, dynamic> json) => PtwUser(
    id: json['id'] as String,
    name: json['name'] as String,
    handle: json['handle'] as String,
    avatarAsset: json['avatarAsset'] as String,
    initialProjectId: json['challengeId'] as String,
  );

  final String id;
  final String name;
  final String handle;
  final String avatarAsset;
  final String initialProjectId;
}
