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
    this.previousMedia,
    this.currentMedia,
    this.progressValue,
    this.metricValue,
    this.previousTimeLabel,
    this.currentTimeLabel,
    this.proofLabel,
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
  final ShareImageValue? previousMedia;
  final ShareImageValue? currentMedia;
  final String? progressValue;
  final String? metricValue;
  final String? previousTimeLabel;
  final String? currentTimeLabel;
  final String? proofLabel;
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
    'previousMedia' => previousMedia,
    'currentMedia' => currentMedia,
    'progressValue' => progressValue,
    'metricValue' => metricValue,
    'previousTimeLabel' => previousTimeLabel,
    'currentTimeLabel' => currentTimeLabel,
    'proofLabel' => proofLabel,
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
    'previousMedia',
    'currentMedia',
    'progressValue',
    'metricValue',
    'previousTimeLabel',
    'currentTimeLabel',
    'proofLabel',
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

enum ShareBackgroundTexture { none, grain, stripes, blobs, iridescent }

/// The user-owned, photo-first treatment applied on top of a theme background.
///
/// All fields are serializable so the exact preview can be restored and used by
/// the PNG exporter. Alignment values are normalized to Flutter's -1...1
/// alignment space; zoom is relative to the background's normal cover fit.
final class ShareBackgroundEdit {
  const ShareBackgroundEdit({
    this.image,
    this.alignmentX = 0,
    this.alignmentY = 0,
    this.zoom = 1,
    this.imageOpacity = 1,
    this.blur = 0,
    this.brightness = 0,
    this.contrast = 1,
    this.saturation = 1,
    this.tintColor = '#FFFFFFFF',
    this.tintOpacity = 0,
    this.overlayColor = '#FF000000',
    this.overlayOpacity = 0,
    this.texture = ShareBackgroundTexture.none,
    this.textureColor = '#FFFFFFFF',
    this.textureSecondaryColor = '#FFBFF7FF',
    this.textureIntensity = 0,
    this.textureScale = 1,
  });

  factory ShareBackgroundEdit.fromJson(Map<String, dynamic> json) {
    final textureName = json['texture'] as String? ?? 'none';
    final textures = ShareBackgroundTexture.values.where(
      (candidate) => candidate.name == textureName,
    );
    if (textures.isEmpty) {
      throw FormatException('Unknown background texture: $textureName');
    }
    return ShareBackgroundEdit(
      image:
          json['image'] == null
              ? null
              : ShareImageValue.fromJson(
                Map<String, dynamic>.from(json['image'] as Map),
              ),
      alignmentX: (json['alignmentX'] as num?)?.toDouble() ?? 0,
      alignmentY: (json['alignmentY'] as num?)?.toDouble() ?? 0,
      zoom: (json['zoom'] as num?)?.toDouble() ?? 1,
      imageOpacity: (json['imageOpacity'] as num?)?.toDouble() ?? 1,
      blur: (json['blur'] as num?)?.toDouble() ?? 0,
      brightness: (json['brightness'] as num?)?.toDouble() ?? 0,
      contrast: (json['contrast'] as num?)?.toDouble() ?? 1,
      saturation: (json['saturation'] as num?)?.toDouble() ?? 1,
      tintColor: json['tintColor'] as String? ?? '#FFFFFFFF',
      tintOpacity: (json['tintOpacity'] as num?)?.toDouble() ?? 0,
      overlayColor: json['overlayColor'] as String? ?? '#FF000000',
      overlayOpacity: (json['overlayOpacity'] as num?)?.toDouble() ?? 0,
      texture: textures.first,
      textureColor: json['textureColor'] as String? ?? '#FFFFFFFF',
      textureSecondaryColor:
          json['textureSecondaryColor'] as String? ?? '#FFBFF7FF',
      textureIntensity: (json['textureIntensity'] as num?)?.toDouble() ?? 0,
      textureScale: (json['textureScale'] as num?)?.toDouble() ?? 1,
    );
  }

  final ShareImageValue? image;
  final double alignmentX;
  final double alignmentY;
  final double zoom;
  final double imageOpacity;
  final double blur;
  final double brightness;
  final double contrast;
  final double saturation;
  final String tintColor;
  final double tintOpacity;
  final String overlayColor;
  final double overlayOpacity;
  final ShareBackgroundTexture texture;
  final String textureColor;
  final String textureSecondaryColor;
  final double textureIntensity;
  final double textureScale;

  ShareBackgroundEdit copyWith({
    ShareImageValue? image,
    bool clearImage = false,
    double? alignmentX,
    double? alignmentY,
    double? zoom,
    double? imageOpacity,
    double? blur,
    double? brightness,
    double? contrast,
    double? saturation,
    String? tintColor,
    double? tintOpacity,
    String? overlayColor,
    double? overlayOpacity,
    ShareBackgroundTexture? texture,
    String? textureColor,
    String? textureSecondaryColor,
    double? textureIntensity,
    double? textureScale,
  }) => ShareBackgroundEdit(
    image: clearImage ? null : image ?? this.image,
    alignmentX: alignmentX ?? this.alignmentX,
    alignmentY: alignmentY ?? this.alignmentY,
    zoom: zoom ?? this.zoom,
    imageOpacity: imageOpacity ?? this.imageOpacity,
    blur: blur ?? this.blur,
    brightness: brightness ?? this.brightness,
    contrast: contrast ?? this.contrast,
    saturation: saturation ?? this.saturation,
    tintColor: tintColor ?? this.tintColor,
    tintOpacity: tintOpacity ?? this.tintOpacity,
    overlayColor: overlayColor ?? this.overlayColor,
    overlayOpacity: overlayOpacity ?? this.overlayOpacity,
    texture: texture ?? this.texture,
    textureColor: textureColor ?? this.textureColor,
    textureSecondaryColor: textureSecondaryColor ?? this.textureSecondaryColor,
    textureIntensity: textureIntensity ?? this.textureIntensity,
    textureScale: textureScale ?? this.textureScale,
  );

  Map<String, dynamic> toJson() => {
    if (image != null) 'image': image!.toJson(),
    'alignmentX': alignmentX,
    'alignmentY': alignmentY,
    'zoom': zoom,
    'imageOpacity': imageOpacity,
    'blur': blur,
    'brightness': brightness,
    'contrast': contrast,
    'saturation': saturation,
    'tintColor': tintColor,
    'tintOpacity': tintOpacity,
    'overlayColor': overlayColor,
    'overlayOpacity': overlayOpacity,
    'texture': texture.name,
    'textureColor': textureColor,
    'textureSecondaryColor': textureSecondaryColor,
    'textureIntensity': textureIntensity,
    'textureScale': textureScale,
  };
}

/// A user-imported image placed in the decoration workspace.
final class SharePlacedOverlayValue {
  const SharePlacedOverlayValue({
    required this.instanceId,
    required this.image,
    required this.centerX,
    required this.centerY,
    required this.scale,
    required this.rotation,
  });

  factory SharePlacedOverlayValue.fromJson(Map<String, dynamic> json) =>
      SharePlacedOverlayValue(
        instanceId: json['instanceId'] as String,
        image: ShareImageValue.fromJson(
          Map<String, dynamic>.from(json['image'] as Map),
        ),
        centerX: (json['centerX'] as num).toDouble(),
        centerY: (json['centerY'] as num).toDouble(),
        scale: (json['scale'] as num).toDouble(),
        rotation: (json['rotation'] as num).toDouble(),
      );

  final String instanceId;
  final ShareImageValue image;
  final double centerX;
  final double centerY;
  final double scale;
  final double rotation;

  SharePlacedOverlayValue copyWith({
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) => SharePlacedOverlayValue(
    instanceId: instanceId,
    image: image,
    centerX: centerX ?? this.centerX,
    centerY: centerY ?? this.centerY,
    scale: scale ?? this.scale,
    rotation: rotation ?? this.rotation,
  );

  Map<String, dynamic> toJson() => {
    'instanceId': instanceId,
    'image': image.toJson(),
    'centerX': centerX,
    'centerY': centerY,
    'scale': scale,
    'rotation': rotation,
  };
}

final class ShareEditorValue {
  ShareEditorValue({
    required this.lookId,
    this.templateId,
    required Map<String, Object?> layerValues,
    required Map<String, ShareLayerTransform> transforms,
    required List<ShareStickerValue> stickers,
    this.backgroundId,
    this.backgroundEdit = const ShareBackgroundEdit(),
    List<SharePlacedOverlayValue> overlays = const [],
    Map<String, Map<String, Object?>> propertyOverrides = const {},
  }) : layerValues = Map<String, Object?>.unmodifiable(layerValues),
       transforms = Map<String, ShareLayerTransform>.unmodifiable(transforms),
       stickers = List.unmodifiable(stickers),
       overlays = List.unmodifiable(overlays),
       propertyOverrides = Map<String, Map<String, Object?>>.unmodifiable({
         for (final entry in propertyOverrides.entries)
           entry.key: Map<String, Object?>.unmodifiable(entry.value),
       });

  factory ShareEditorValue.fromJson(Map<String, dynamic> json) =>
      ShareEditorValue(
        lookId: json['lookId'] as String,
        templateId: json['templateId'] as String?,
        backgroundId: json['backgroundId'] as String?,
        backgroundEdit:
            json['backgroundEdit'] == null
                ? const ShareBackgroundEdit()
                : ShareBackgroundEdit.fromJson(
                  Map<String, dynamic>.from(json['backgroundEdit'] as Map),
                ),
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
        overlays: ((json['overlays'] as List<dynamic>?) ?? const [])
            .map(
              (value) => SharePlacedOverlayValue.fromJson(
                Map<String, dynamic>.from(value as Map),
              ),
            )
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
  final String? templateId;
  final String? backgroundId;
  final ShareBackgroundEdit backgroundEdit;
  final Map<String, Object?> layerValues;
  final Map<String, ShareLayerTransform> transforms;
  final List<ShareStickerValue> stickers;
  final List<SharePlacedOverlayValue> overlays;
  final Map<String, Map<String, Object?>> propertyOverrides;

  ShareEditorValue copyWith({
    String? lookId,
    String? templateId,
    String? backgroundId,
    bool clearBackground = false,
    ShareBackgroundEdit? backgroundEdit,
    Map<String, Object?>? layerValues,
    Map<String, ShareLayerTransform>? transforms,
    List<ShareStickerValue>? stickers,
    List<SharePlacedOverlayValue>? overlays,
    Map<String, Map<String, Object?>>? propertyOverrides,
  }) => ShareEditorValue(
    lookId: lookId ?? this.lookId,
    templateId: templateId ?? this.templateId,
    backgroundId: clearBackground ? null : backgroundId ?? this.backgroundId,
    backgroundEdit: backgroundEdit ?? this.backgroundEdit,
    layerValues: layerValues ?? this.layerValues,
    transforms: transforms ?? this.transforms,
    stickers: stickers ?? this.stickers,
    overlays: overlays ?? this.overlays,
    propertyOverrides: propertyOverrides ?? this.propertyOverrides,
  );

  Map<String, dynamic> toJson() => {
    'lookId': lookId,
    if (templateId != null) 'templateId': templateId,
    'backgroundId': backgroundId,
    'backgroundEdit': backgroundEdit.toJson(),
    'layerValues': layerValues.map(
      (key, value) => MapEntry(key, _encodeValue(value)),
    ),
    'transforms': transforms.map((key, value) => MapEntry(key, value.toJson())),
    'stickers': stickers.map((item) => item.toJson()).toList(),
    'overlays': overlays.map((item) => item.toJson()).toList(),
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
