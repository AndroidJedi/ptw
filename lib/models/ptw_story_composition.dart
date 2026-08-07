import 'ptw_image_ref.dart';

enum PtwStoryTextTreatment { clean, sticker, night, candy, chaos, victory }

final class PtwStoryStickerPlacement {
  const PtwStoryStickerPlacement({
    required this.instanceId,
    required this.stickerId,
    required this.centerX,
    required this.centerY,
    required this.scale,
    required this.rotation,
  });

  factory PtwStoryStickerPlacement.fromJson(Map<String, dynamic> json) =>
      PtwStoryStickerPlacement(
        instanceId: json['instanceId'] as String,
        stickerId: json['stickerId'] as String,
        centerX: (json['centerX'] as num).toDouble(),
        centerY: (json['centerY'] as num).toDouble(),
        scale: (json['scale'] as num).toDouble(),
        rotation: (json['rotation'] as num).toDouble(),
      );

  static const minimumScale = 0.12;
  static const maximumScale = 0.42;

  final String instanceId;
  final String stickerId;
  final double centerX;
  final double centerY;
  final double scale;
  final double rotation;

  PtwStoryStickerPlacement copyWith({
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) => PtwStoryStickerPlacement(
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

/// The exact, serializable Story shown to the creator and exported for sharing.
final class PtwStoryComposition {
  PtwStoryComposition({
    required this.projectId,
    required this.eventName,
    required this.headline,
    required this.dare,
    required this.avatar,
    required this.projectBackground,
    required this.lookId,
    required this.textTreatment,
    required this.caption,
    required this.createdAt,
    required this.updatedAt,
    required List<PtwStoryStickerPlacement> stickers,
    this.momentId,
    this.backgroundId,
    this.themeId = 'ptw_story_v1',
    this.themeSchemaVersion = 1,
    this.editorValue,
  }) : stickers = List.unmodifiable(stickers);

  factory PtwStoryComposition.fromJson(
    Map<String, dynamic> json, {
    bool migrateGeneratedValue = false,
  }) {
    final editorValue =
        json['editorValue'] == null
            ? migrateGeneratedValue
                ? _migrateFixedEditorValue(json)
                : null
            : Map<String, dynamic>.from(
              json['editorValue'] as Map<String, dynamic>,
            );
    return PtwStoryComposition(
      projectId: json['projectId'] as String,
      eventName: json['eventName'] as String,
      momentId: json['momentId'] as String?,
      headline: json['headline'] as String,
      dare: json['dare'] as String,
      avatar: PtwImageRef.fromJson(json['avatar'] as Map<String, dynamic>),
      projectBackground: PtwImageRef.fromJson(
        json['projectBackground'] as Map<String, dynamic>,
      ),
      backgroundId: json['backgroundId'] as String?,
      themeId: json['themeId'] as String? ?? 'ptw_story_v1',
      themeSchemaVersion: json['themeSchemaVersion'] as int? ?? 1,
      editorValue: editorValue,
      lookId: json['lookId'] as String,
      textTreatment: PtwStoryTextTreatment.values.byName(
        json['textTreatment'] as String,
      ),
      stickers:
          (json['stickers'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map(PtwStoryStickerPlacement.fromJson)
              .toList(),
      caption: json['caption'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
    );
  }

  static const maximumHeadlineLength = 90;
  static const maximumDareLength = 48;

  final String projectId;
  final String eventName;
  final String? momentId;
  final String headline;
  final String dare;
  final PtwImageRef avatar;
  final PtwImageRef projectBackground;
  final String? backgroundId;
  final String themeId;
  final int themeSchemaVersion;
  final Map<String, dynamic>? editorValue;
  final String lookId;
  final PtwStoryTextTreatment textTreatment;
  final List<PtwStoryStickerPlacement> stickers;
  final String caption;
  final DateTime createdAt;
  final DateTime updatedAt;

  String get publicLink => 'https://ptw.to/p/$projectId';

  PtwStoryComposition copyWith({
    String? headline,
    String? dare,
    String? backgroundId,
    bool clearBackgroundId = false,
    String? lookId,
    PtwStoryTextTreatment? textTreatment,
    List<PtwStoryStickerPlacement>? stickers,
    String? caption,
    DateTime? updatedAt,
    Map<String, dynamic>? editorValue,
  }) => PtwStoryComposition(
    projectId: projectId,
    eventName: eventName,
    momentId: momentId,
    headline: headline ?? this.headline,
    dare: dare ?? this.dare,
    avatar: avatar,
    projectBackground: projectBackground,
    backgroundId: clearBackgroundId ? null : backgroundId ?? this.backgroundId,
    themeId: themeId,
    themeSchemaVersion: themeSchemaVersion,
    editorValue: editorValue ?? this.editorValue,
    lookId: lookId ?? this.lookId,
    textTreatment: textTreatment ?? this.textTreatment,
    stickers: stickers ?? this.stickers,
    caption: caption ?? this.caption,
    createdAt: createdAt,
    updatedAt: updatedAt ?? this.updatedAt,
  );

  Map<String, dynamic> toJson() => {
    'projectId': projectId,
    'eventName': eventName,
    'momentId': momentId,
    'headline': headline,
    'dare': dare,
    'avatar': avatar.toJson(),
    'projectBackground': projectBackground.toJson(),
    'backgroundId': backgroundId,
    'themeId': themeId,
    'themeSchemaVersion': themeSchemaVersion,
    'editorValue': editorValue,
    'lookId': lookId,
    'textTreatment': textTreatment.name,
    'stickers': stickers.map((item) => item.toJson()).toList(),
    'caption': caption,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
  };
}

Map<String, dynamic> _migrateFixedEditorValue(Map<String, dynamic> json) {
  final avatar = Map<String, dynamic>.from(
    json['avatar'] as Map<String, dynamic>,
  );
  return {
    'lookId': json['lookId'] as String,
    'backgroundId': json['backgroundId'] as String? ?? 'project_cover',
    'layerValues': {
      'headline': json['headline'] as String,
      'secondary': json['dare'] as String,
      'avatar': {'\$type': 'image', ...avatar},
      'brand': 'PTW',
      'tagline': 'PROVE THEM WRONG',
    },
    'transforms': <String, dynamic>{},
    'stickers': [
      for (final sticker in (json['stickers'] as List<dynamic>))
        Map<String, dynamic>.from(sticker as Map<String, dynamic>),
    ],
    'propertyOverrides': <String, dynamic>{},
  };
}
