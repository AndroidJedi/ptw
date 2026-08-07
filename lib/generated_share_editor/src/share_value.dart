import 'dart:convert';
import 'dart:typed_data';

enum ShareImageSource { asset, memory, network, file }

final class ShareImageValue {
  const ShareImageValue._({
    required this.source,
    this.path,
    this.bytes,
    this.mimeType,
  });

  const ShareImageValue.asset(String path)
    : this._(source: ShareImageSource.asset, path: path);

  const ShareImageValue.network(String path)
    : this._(source: ShareImageSource.network, path: path);

  const ShareImageValue.file(String path)
    : this._(source: ShareImageSource.file, path: path);

  const ShareImageValue.memory(Uint8List bytes, {required String mimeType})
    : this._(source: ShareImageSource.memory, bytes: bytes, mimeType: mimeType);

  factory ShareImageValue.fromJson(Map<String, dynamic> json) {
    final rawSource = json['source'];
    if (rawSource is! String) {
      throw const FormatException('Image source must be a string');
    }
    final sources = ShareImageSource.values.where(
      (candidate) => candidate.name == rawSource,
    );
    if (sources.isEmpty) {
      throw FormatException('Unknown image source: $rawSource');
    }
    final image = ShareImageValue._(
      source: sources.first,
      path: json['path'] as String?,
      bytes:
          json['bytes'] == null ? null : base64Decode(json['bytes'] as String),
      mimeType: json['mimeType'] as String?,
    );
    if (image.source == ShareImageSource.memory) {
      if (image.bytes == null ||
          image.bytes!.isEmpty ||
          image.mimeType == null ||
          image.mimeType!.isEmpty) {
        throw const FormatException(
          'Memory images require bytes and a MIME type',
        );
      }
    } else if (image.path == null || image.path!.trim().isEmpty) {
      throw const FormatException(
        'Asset, file, and network images need a path',
      );
    }
    return image;
  }

  final ShareImageSource source;
  final String? path;
  final Uint8List? bytes;
  final String? mimeType;

  Map<String, dynamic> toJson() => {
    'source': source.name,
    if (path != null) 'path': path,
    if (bytes != null) 'bytes': base64Encode(bytes!),
    if (mimeType != null) 'mimeType': mimeType,
  };
}

final class ShareEditorContent {
  const ShareEditorContent({
    required this.projectId,
    required this.headline,
    required this.secondaryText,
    required this.ownerName,
    required this.ownerHandle,
    required this.avatar,
    required this.cover,
    required this.caption,
    required this.publicLink,
    this.custom = const {},
  });

  final String projectId;
  final String headline;
  final String secondaryText;
  final String ownerName;
  final String ownerHandle;
  final ShareImageValue avatar;
  final ShareImageValue cover;
  final String caption;
  final String publicLink;
  final Map<String, Object?> custom;

  Object? resolve(String binding) => switch (binding) {
    'projectId' => projectId,
    'headline' => headline,
    'secondaryText' => secondaryText,
    'ownerName' => ownerName,
    'ownerHandle' => ownerHandle,
    'avatar' => avatar,
    'cover' => cover,
    'caption' => caption,
    'publicLink' => publicLink,
    _ when binding.startsWith('custom.') => custom[binding.substring(7)],
    _ => null,
  };

  static const knownBindings = <String>{
    'projectId',
    'headline',
    'secondaryText',
    'ownerName',
    'ownerHandle',
    'avatar',
    'cover',
    'caption',
    'publicLink',
  };
}

final class ShareLayerTransform {
  const ShareLayerTransform({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    this.rotation = 0,
  });

  factory ShareLayerTransform.fromJson(Map<String, dynamic> json) =>
      ShareLayerTransform(
        x: (json['x'] as num).toDouble(),
        y: (json['y'] as num).toDouble(),
        width: (json['width'] as num).toDouble(),
        height: (json['height'] as num).toDouble(),
        rotation: (json['rotation'] as num?)?.toDouble() ?? 0,
      );

  final double x;
  final double y;
  final double width;
  final double height;
  final double rotation;

  ShareLayerTransform copyWith({
    double? x,
    double? y,
    double? width,
    double? height,
    double? rotation,
  }) => ShareLayerTransform(
    x: x ?? this.x,
    y: y ?? this.y,
    width: width ?? this.width,
    height: height ?? this.height,
    rotation: rotation ?? this.rotation,
  );

  Map<String, dynamic> toJson() => {
    'x': x,
    'y': y,
    'width': width,
    'height': height,
    'rotation': rotation,
  };
}

final class ShareStickerValue {
  const ShareStickerValue({
    required this.instanceId,
    required this.stickerId,
    required this.centerX,
    required this.centerY,
    required this.scale,
    required this.rotation,
  });

  factory ShareStickerValue.fromJson(Map<String, dynamic> json) =>
      ShareStickerValue(
        instanceId: json['instanceId'] as String,
        stickerId: json['stickerId'] as String,
        centerX: (json['centerX'] as num).toDouble(),
        centerY: (json['centerY'] as num).toDouble(),
        scale: (json['scale'] as num).toDouble(),
        rotation: (json['rotation'] as num).toDouble(),
      );

  final String instanceId;
  final String stickerId;
  final double centerX;
  final double centerY;
  final double scale;
  final double rotation;

  ShareStickerValue copyWith({
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) => ShareStickerValue(
    instanceId: instanceId,
    stickerId: stickerId,
    centerX: centerX ?? this.centerX,
    centerY: centerY ?? this.centerY,
    scale: scale ?? this.scale,
    rotation: rotation ?? this.rotation,
  );

  Map<String, dynamic> toJson() => {
    'instanceId': instanceId,
    'stickerId': stickerId,
    'centerX': centerX,
    'centerY': centerY,
    'scale': scale,
    'rotation': rotation,
  };
}

final class ShareEditorValue {
  ShareEditorValue({
    required this.lookId,
    required Map<String, Object?> layerValues,
    required Map<String, ShareLayerTransform> transforms,
    required List<ShareStickerValue> stickers,
    this.backgroundId,
    Map<String, Map<String, Object?>> propertyOverrides = const {},
  }) : layerValues = Map<String, Object?>.unmodifiable(layerValues),
       transforms = Map<String, ShareLayerTransform>.unmodifiable(transforms),
       stickers = List.unmodifiable(stickers),
       propertyOverrides = Map<String, Map<String, Object?>>.unmodifiable({
         for (final entry in propertyOverrides.entries)
           entry.key: Map<String, Object?>.unmodifiable(entry.value),
       });

  factory ShareEditorValue.fromJson(Map<String, dynamic> json) =>
      ShareEditorValue(
        lookId: json['lookId'] as String,
        backgroundId: json['backgroundId'] as String?,
        layerValues: (json['layerValues'] as Map<String, dynamic>).map(
          (key, value) => MapEntry(key, _decodeValue(value)),
        ),
        transforms: (json['transforms'] as Map<String, dynamic>).map(
          (key, value) => MapEntry(
            key,
            ShareLayerTransform.fromJson(value as Map<String, dynamic>),
          ),
        ),
        stickers: (json['stickers'] as List<dynamic>)
            .cast<Map<String, dynamic>>()
            .map(ShareStickerValue.fromJson)
            .toList(growable: false),
        propertyOverrides:
            ((json['propertyOverrides'] as Map<String, dynamic>?) ?? const {})
                .map(
                  (key, value) => MapEntry(
                    key,
                    Map<String, Object?>.from(value as Map<String, dynamic>),
                  ),
                ),
      );

  final String lookId;
  final String? backgroundId;
  final Map<String, Object?> layerValues;
  final Map<String, ShareLayerTransform> transforms;
  final List<ShareStickerValue> stickers;
  final Map<String, Map<String, Object?>> propertyOverrides;

  ShareEditorValue copyWith({
    String? lookId,
    String? backgroundId,
    bool clearBackground = false,
    Map<String, Object?>? layerValues,
    Map<String, ShareLayerTransform>? transforms,
    List<ShareStickerValue>? stickers,
    Map<String, Map<String, Object?>>? propertyOverrides,
  }) => ShareEditorValue(
    lookId: lookId ?? this.lookId,
    backgroundId: clearBackground ? null : backgroundId ?? this.backgroundId,
    layerValues: layerValues ?? this.layerValues,
    transforms: transforms ?? this.transforms,
    stickers: stickers ?? this.stickers,
    propertyOverrides: propertyOverrides ?? this.propertyOverrides,
  );

  Map<String, dynamic> toJson() => {
    'lookId': lookId,
    'backgroundId': backgroundId,
    'layerValues': layerValues.map(
      (key, value) => MapEntry(key, _encodeValue(value)),
    ),
    'transforms': transforms.map((key, value) => MapEntry(key, value.toJson())),
    'stickers': stickers.map((item) => item.toJson()).toList(),
    'propertyOverrides': propertyOverrides,
  };
}

Object? _encodeValue(Object? value) {
  if (value is ShareImageValue) {
    return {'\$type': 'image', ...value.toJson()};
  }
  if (value is List<Object?>) return value.map(_encodeValue).toList();
  if (value is Map<String, Object?>) {
    return value.map((key, child) => MapEntry(key, _encodeValue(child)));
  }
  return value;
}

Object? _decodeValue(Object? value) {
  if (value is Map<String, dynamic>) {
    if (value['\$type'] == 'image') return ShareImageValue.fromJson(value);
    return value.map((key, child) => MapEntry(key, _decodeValue(child)));
  }
  if (value is List<dynamic>) return value.map(_decodeValue).toList();
  return value;
}
