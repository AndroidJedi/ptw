/// A selectable local photograph for a newly created public promise.
final class PtwPostBackground {
  const PtwPostBackground({
    required this.id,
    required this.label,
    required this.asset,
  });

  factory PtwPostBackground.fromJson(Map<String, dynamic> json) =>
      PtwPostBackground(
        id: json['id'] as String,
        label: json['label'] as String,
        asset: json['asset'] as String,
      );

  final String id;
  final String label;
  final String asset;
}
