enum PtwImageSource { asset, file }

/// Serializable reference to either bundled artwork or imported local media.
final class PtwImageRef {
  const PtwImageRef({required this.source, required this.path});

  const PtwImageRef.asset(String path)
    : this(source: PtwImageSource.asset, path: path);

  const PtwImageRef.file(String path)
    : this(source: PtwImageSource.file, path: path);

  factory PtwImageRef.fromJson(Map<String, dynamic> json) => PtwImageRef(
    source: PtwImageSource.values.byName(json['source'] as String),
    path: json['path'] as String,
  );

  final PtwImageSource source;
  final String path;

  Map<String, dynamic> toJson() => {'source': source.name, 'path': path};
}
