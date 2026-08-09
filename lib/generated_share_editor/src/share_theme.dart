import 'dart:convert';

import 'share_theme_asset_loader_stub.dart'
    if (dart.library.ui) 'share_theme_asset_loader_flutter.dart'
    as asset_loader;
import 'share_value.dart';

enum ShareTemplateFamily {
  unassigned,
  heroPhoto,
  progress,
  comparison,
  proof,
  conflict,
  milestone,
  documentary,
  reflection,
  recovery,
  result,
}

enum ShareJourneyState {
  unassigned,
  beginning,
  grinding,
  smallWin,
  milestone,
  failure,
  recovery,
  reflection,
  finish;

  @Deprecated('Use grinding')
  static const grind = grinding;

  @Deprecated('Use failure')
  static const setback = failure;

  @Deprecated('Use finish')
  static const result = finish;

  String get label => switch (this) {
    unassigned => 'Choose stage',
    beginning => 'Beginning',
    grinding => 'Grinding',
    smallWin => 'Small Win',
    milestone => 'Milestone',
    failure => 'Failure',
    recovery => 'Recovery',
    reflection => 'Reflection',
    finish => 'Finish',
  };
}

enum ShareAnimationPreset { none, fade, slideUp, scaleIn, reveal }

final class ShareAnimationSpec {
  const ShareAnimationSpec({
    this.preset = ShareAnimationPreset.none,
    this.delayMilliseconds = 0,
    this.durationMilliseconds = 300,
    this.easing = 'easeOut',
  });

  factory ShareAnimationSpec.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ShareAnimationSpec();
    return ShareAnimationSpec(
      preset: _enumValue(
        ShareAnimationPreset.values,
        json['preset'],
        'animation preset',
        fallback: ShareAnimationPreset.none,
      ),
      delayMilliseconds: (json['delayMilliseconds'] as num?)?.toInt() ?? 0,
      durationMilliseconds:
          (json['durationMilliseconds'] as num?)?.toInt() ?? 300,
      easing: json['easing'] as String? ?? 'easeOut',
    );
  }

  final ShareAnimationPreset preset;
  final int delayMilliseconds;
  final int durationMilliseconds;
  final String easing;

  Map<String, dynamic> toJson() => {
    'preset': preset.name,
    'delayMilliseconds': delayMilliseconds,
    'durationMilliseconds': durationMilliseconds,
    'easing': easing,
  };
}

enum ShareSemanticRole {
  unassigned,
  heroMedia,
  previousMedia,
  currentMedia,
  headline,
  challenge,
  criticism,
  proof,
  metric,
  progress,
  time,
  goal,
  avatar,
  brand,
  semanticDecoration,
}

enum ShareLayerEmphasis { primary, secondary, tertiary }

enum ShareSafeZoneKind {
  instagramTopDanger,
  instagramBottomDanger,
  recommendedLink,
  protectedSubject,
  brandSafe,
}

enum ShareTemplateStatus { experimental, production }

final class ShareLayerRuntimePermissions {
  const ShareLayerRuntimePermissions({
    this.canEditContent = false,
    this.canReplaceMedia = false,
    this.canCropMedia = false,
    this.canMove = false,
    this.canResize = false,
    this.canRotate = false,
    this.canStyle = false,
    this.canHide = false,
  });

  factory ShareLayerRuntimePermissions.fromJson(Map<String, dynamic>? json) {
    final source = json ?? const <String, dynamic>{};
    return ShareLayerRuntimePermissions(
      canEditContent: source['canEditContent'] as bool? ?? false,
      canReplaceMedia: source['canReplaceMedia'] as bool? ?? false,
      canCropMedia: source['canCropMedia'] as bool? ?? false,
      canMove: source['canMove'] as bool? ?? false,
      canResize: source['canResize'] as bool? ?? false,
      canRotate: source['canRotate'] as bool? ?? false,
      canStyle: source['canStyle'] as bool? ?? false,
      canHide: source['canHide'] as bool? ?? false,
    );
  }

  final bool canEditContent;
  final bool canReplaceMedia;
  final bool canCropMedia;
  final bool canMove;
  final bool canResize;
  final bool canRotate;
  final bool canStyle;
  final bool canHide;

  ShareLayerRuntimePermissions copyWith({
    bool? canEditContent,
    bool? canReplaceMedia,
    bool? canCropMedia,
    bool? canMove,
    bool? canResize,
    bool? canRotate,
    bool? canStyle,
    bool? canHide,
  }) => ShareLayerRuntimePermissions(
    canEditContent: canEditContent ?? this.canEditContent,
    canReplaceMedia: canReplaceMedia ?? this.canReplaceMedia,
    canCropMedia: canCropMedia ?? this.canCropMedia,
    canMove: canMove ?? this.canMove,
    canResize: canResize ?? this.canResize,
    canRotate: canRotate ?? this.canRotate,
    canStyle: canStyle ?? this.canStyle,
    canHide: canHide ?? this.canHide,
  );

  Map<String, dynamic> toJson() => {
    'canEditContent': canEditContent,
    'canReplaceMedia': canReplaceMedia,
    'canCropMedia': canCropMedia,
    'canMove': canMove,
    'canResize': canResize,
    'canRotate': canRotate,
    'canStyle': canStyle,
    'canHide': canHide,
  };
}

final class ShareTemplateRuntimePermissions {
  const ShareTemplateRuntimePermissions({
    this.userCanReplaceMedia = false,
    this.userCanCropMedia = false,
    this.userCanEditHeadline = false,
    this.userCanEditProofValue = false,
    this.userCanChooseAlternateTemplate = false,
    this.userCanHideOptionalNote = false,
    this.userCanEditDecorations = false,
  });

  factory ShareTemplateRuntimePermissions.fromJson(Map<String, dynamic>? json) {
    final source = json ?? const <String, dynamic>{};
    return ShareTemplateRuntimePermissions(
      userCanReplaceMedia: source['userCanReplaceMedia'] as bool? ?? false,
      userCanCropMedia: source['userCanCropMedia'] as bool? ?? false,
      userCanEditHeadline: source['userCanEditHeadline'] as bool? ?? false,
      userCanEditProofValue: source['userCanEditProofValue'] as bool? ?? false,
      userCanChooseAlternateTemplate:
          source['userCanChooseAlternateTemplate'] as bool? ?? false,
      userCanHideOptionalNote:
          source['userCanHideOptionalNote'] as bool? ?? false,
      userCanEditDecorations:
          source['userCanEditDecorations'] as bool? ?? false,
    );
  }

  final bool userCanReplaceMedia;
  final bool userCanCropMedia;
  final bool userCanEditHeadline;
  final bool userCanEditProofValue;
  final bool userCanChooseAlternateTemplate;
  final bool userCanHideOptionalNote;
  final bool userCanEditDecorations;

  ShareTemplateRuntimePermissions copyWith({
    bool? userCanReplaceMedia,
    bool? userCanCropMedia,
    bool? userCanEditHeadline,
    bool? userCanEditProofValue,
    bool? userCanChooseAlternateTemplate,
    bool? userCanHideOptionalNote,
    bool? userCanEditDecorations,
  }) => ShareTemplateRuntimePermissions(
    userCanReplaceMedia: userCanReplaceMedia ?? this.userCanReplaceMedia,
    userCanCropMedia: userCanCropMedia ?? this.userCanCropMedia,
    userCanEditHeadline: userCanEditHeadline ?? this.userCanEditHeadline,
    userCanEditProofValue: userCanEditProofValue ?? this.userCanEditProofValue,
    userCanChooseAlternateTemplate:
        userCanChooseAlternateTemplate ?? this.userCanChooseAlternateTemplate,
    userCanHideOptionalNote:
        userCanHideOptionalNote ?? this.userCanHideOptionalNote,
    userCanEditDecorations:
        userCanEditDecorations ?? this.userCanEditDecorations,
  );

  Map<String, dynamic> toJson() => {
    'userCanReplaceMedia': userCanReplaceMedia,
    'userCanCropMedia': userCanCropMedia,
    'userCanEditHeadline': userCanEditHeadline,
    'userCanEditProofValue': userCanEditProofValue,
    'userCanChooseAlternateTemplate': userCanChooseAlternateTemplate,
    'userCanHideOptionalNote': userCanHideOptionalNote,
    'userCanEditDecorations': userCanEditDecorations,
  };
}

final class ShareSafeZoneConfig {
  const ShareSafeZoneConfig({
    required this.id,
    required this.label,
    required this.kind,
    required this.rect,
  });

  factory ShareSafeZoneConfig.fromJson(Map<String, dynamic> json) =>
      ShareSafeZoneConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        kind: _enumValue(
          ShareSafeZoneKind.values,
          json['kind'],
          'safe-zone kind',
        ),
        rect: ShareLayerTransform.fromJson(_map(json, 'rect')),
      );

  final String id;
  final String label;
  final ShareSafeZoneKind kind;
  final ShareLayerTransform rect;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'kind': kind.name,
    'rect': rect.toJson(),
  };
}

final class ShareTemplateConfig {
  ShareTemplateConfig({
    required this.id,
    required this.label,
    required this.family,
    required this.variant,
    required this.narrativeIntent,
    required this.primaryJourneyState,
    required Set<ShareJourneyState> supportedJourneyStates,
    required Set<ShareSemanticRole> requiredContentRoles,
    required Set<ShareSemanticRole> optionalContentRoles,
    required this.runtimePermissions,
    required this.primaryAnchor,
    required this.supportedMediaCount,
    required this.supportsComparison,
    required this.supportsProof,
    required List<ShareSafeZoneConfig> safeZones,
    required this.designSystemVersion,
    required this.templateVersion,
    required this.status,
    Map<String, Map<String, Object?>> layerOverrides = const {},
    this.animation = const ShareAnimationSpec(),
    this.accentColorToken = 'ptwAccent',
    this.mediaCoverage = 0.85,
  }) : supportedJourneyStates = Set.unmodifiable(supportedJourneyStates),
       requiredContentRoles = Set.unmodifiable(requiredContentRoles),
       optionalContentRoles = Set.unmodifiable(optionalContentRoles),
       safeZones = List.unmodifiable(safeZones),
       layerOverrides = Map<String, Map<String, Object?>>.unmodifiable({
         for (final entry in layerOverrides.entries)
           entry.key: Map<String, Object?>.unmodifiable(entry.value),
       });

  factory ShareTemplateConfig.fromJson(Map<String, dynamic> json) =>
      ShareTemplateConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        family: _enumValue(
          ShareTemplateFamily.values,
          json['family'],
          'template family',
        ),
        variant: _string(json, 'variant'),
        narrativeIntent: _string(json, 'narrativeIntent'),
        primaryJourneyState: _journeyState(
          json['primaryJourneyState'],
          'primary journey state',
        ),
        supportedJourneyStates: _journeyStateSet(
          json['supportedJourneyStates'],
          'supported journey states',
        ),
        requiredContentRoles: _enumSet(
          ShareSemanticRole.values,
          json['requiredContentRoles'],
          'required content roles',
        ),
        optionalContentRoles: _enumSet(
          ShareSemanticRole.values,
          json['optionalContentRoles'],
          'optional content roles',
        ),
        runtimePermissions: ShareTemplateRuntimePermissions.fromJson(
          _mapOrNull(json['runtimePermissions']),
        ),
        primaryAnchor: _enumValue(
          ShareSemanticRole.values,
          json['primaryAnchor'],
          'primary anchor',
        ),
        supportedMediaCount: _int(json, 'supportedMediaCount'),
        supportsComparison: json['supportsComparison'] as bool? ?? false,
        supportsProof: json['supportsProof'] as bool? ?? false,
        safeZones:
            _list(
              json['safeZones'],
            ).map(_object).map(ShareSafeZoneConfig.fromJson).toList(),
        designSystemVersion: _string(json, 'designSystemVersion'),
        templateVersion: _int(json, 'templateVersion'),
        status: _enumValue(
          ShareTemplateStatus.values,
          json['status'],
          'template status',
        ),
        layerOverrides: _mapOrEmpty(json['layerOverrides']).map(
          (key, value) => MapEntry(
            key,
            Map<String, Object?>.from(value as Map<String, dynamic>),
          ),
        ),
        animation: ShareAnimationSpec.fromJson(_mapOrNull(json['animation'])),
        accentColorToken: json['accentColorToken'] as String? ?? 'ptwAccent',
        mediaCoverage: (json['mediaCoverage'] as num?)?.toDouble() ?? 0.85,
      );

  final String id;
  final String label;
  final ShareTemplateFamily family;
  final String variant;
  final String narrativeIntent;
  final ShareJourneyState primaryJourneyState;
  final Set<ShareJourneyState> supportedJourneyStates;
  final Set<ShareSemanticRole> requiredContentRoles;
  final Set<ShareSemanticRole> optionalContentRoles;
  final ShareTemplateRuntimePermissions runtimePermissions;
  final ShareSemanticRole primaryAnchor;
  final int supportedMediaCount;
  final bool supportsComparison;
  final bool supportsProof;
  final List<ShareSafeZoneConfig> safeZones;
  final String designSystemVersion;
  final int templateVersion;
  final ShareTemplateStatus status;
  final Map<String, Map<String, Object?>> layerOverrides;
  final ShareAnimationSpec animation;
  final String accentColorToken;
  final double mediaCoverage;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'family': family.name,
    'variant': variant,
    'narrativeIntent': narrativeIntent,
    'primaryJourneyState': primaryJourneyState.name,
    'supportedJourneyStates':
        supportedJourneyStates.map((item) => item.name).toList()..sort(),
    'requiredContentRoles':
        requiredContentRoles.map((item) => item.name).toList()..sort(),
    'optionalContentRoles':
        optionalContentRoles.map((item) => item.name).toList()..sort(),
    'runtimePermissions': runtimePermissions.toJson(),
    'primaryAnchor': primaryAnchor.name,
    'supportedMediaCount': supportedMediaCount,
    'supportsComparison': supportsComparison,
    'supportsProof': supportsProof,
    'safeZones': safeZones.map((item) => item.toJson()).toList(),
    'designSystemVersion': designSystemVersion,
    'templateVersion': templateVersion,
    'status': status.name,
    'layerOverrides': layerOverrides,
    'animation': animation.toJson(),
    'accentColorToken': accentColorToken,
    'mediaCoverage': mediaCoverage,
  };
}

enum ShareAccessMode { free, premiumVisible, premiumHidden }

final class ShareAccessPolicy {
  const ShareAccessPolicy({
    this.mode = ShareAccessMode.free,
    this.entitlementKey,
  });

  factory ShareAccessPolicy.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ShareAccessPolicy();
    final rawMode = _string(json, 'mode');
    final mode = ShareAccessMode.values.where(
      (candidate) => candidate.name == rawMode,
    );
    if (mode.isEmpty) {
      throw FormatException('Unknown access mode: $rawMode');
    }
    final key = json['entitlementKey'] as String?;
    if (mode.first != ShareAccessMode.free &&
        (key == null || key.trim().isEmpty)) {
      throw const FormatException(
        'Premium access policies require an entitlementKey',
      );
    }
    return ShareAccessPolicy(mode: mode.first, entitlementKey: key);
  }

  final ShareAccessMode mode;
  final String? entitlementKey;

  Map<String, dynamic> toJson() => {
    'mode': mode.name,
    if (entitlementKey != null) 'entitlementKey': entitlementKey,
  };
}

enum ShareControlKind { action, text, number, color, choice, toggle }

final class ShareControlConfig {
  const ShareControlConfig({
    required this.id,
    required this.label,
    required this.kind,
    String? capability,
    this.defaultValue,
    this.minimum,
    this.maximum,
    this.options = const [],
    this.access = const ShareAccessPolicy(),
  }) : capability = capability ?? id;

  factory ShareControlConfig.fromJson(Map<String, dynamic> json) {
    final rawKind = _string(json, 'kind');
    final kinds = ShareControlKind.values.where(
      (candidate) => candidate.name == rawKind,
    );
    if (kinds.isEmpty) {
      throw FormatException('Unknown control kind: $rawKind');
    }
    return ShareControlConfig(
      id: _string(json, 'id'),
      label: _string(json, 'label'),
      kind: kinds.first,
      capability: json['capability'] as String?,
      defaultValue: json['default'],
      minimum: (json['minimum'] as num?)?.toDouble(),
      maximum: (json['maximum'] as num?)?.toDouble(),
      options: _list(json['options']).map((item) => item.toString()).toList(),
      access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
    );
  }

  final String id;
  final String label;
  final ShareControlKind kind;
  final String capability;
  final Object? defaultValue;
  final double? minimum;
  final double? maximum;
  final List<String> options;
  final ShareAccessPolicy access;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'kind': kind.name,
    'capability': capability,
    'default': defaultValue,
    if (minimum != null) 'minimum': minimum,
    if (maximum != null) 'maximum': maximum,
    if (options.isNotEmpty) 'options': options,
    'access': access.toJson(),
  };
}

final class ShareCanvasConfig {
  const ShareCanvasConfig({
    required this.width,
    required this.height,
    required this.outputWidth,
    required this.outputHeight,
    this.safeInset = 0,
    this.cornerRadius = 0,
  });

  factory ShareCanvasConfig.fromJson(Map<String, dynamic> json) =>
      ShareCanvasConfig(
        width: _double(json, 'width'),
        height: _double(json, 'height'),
        outputWidth: _int(json, 'outputWidth'),
        outputHeight: _int(json, 'outputHeight'),
        safeInset: (json['safeInset'] as num?)?.toDouble() ?? 0,
        cornerRadius: (json['cornerRadius'] as num?)?.toDouble() ?? 0,
      );

  final double width;
  final double height;
  final int outputWidth;
  final int outputHeight;
  final double safeInset;
  final double cornerRadius;

  Map<String, dynamic> toJson() => {
    'width': width,
    'height': height,
    'outputWidth': outputWidth,
    'outputHeight': outputHeight,
    'safeInset': safeInset,
    'cornerRadius': cornerRadius,
  };
}

final class ShareAssetConfig {
  const ShareAssetConfig({
    required this.id,
    required this.kind,
    required this.mimeType,
    this.path,
    this.data,
    this.fontFamily,
    this.fontWeight,
    this.italic = false,
  });

  factory ShareAssetConfig.fromJson(Map<String, dynamic> json) =>
      ShareAssetConfig(
        id: _string(json, 'id'),
        kind: _string(json, 'kind'),
        mimeType: _string(json, 'mimeType'),
        path: json['path'] as String?,
        data: json['data'] as String?,
        fontFamily: json['fontFamily'] as String?,
        fontWeight: json['fontWeight'] as int?,
        italic: json['italic'] as bool? ?? false,
      );

  final String id;
  final String kind;
  final String mimeType;
  final String? path;
  final String? data;
  final String? fontFamily;
  final int? fontWeight;
  final bool italic;

  Uint8List? get embeddedBytes => data == null ? null : base64Decode(data!);

  Map<String, dynamic> toJson() => {
    'id': id,
    'kind': kind,
    'mimeType': mimeType,
    if (path != null) 'path': path,
    if (data != null) 'data': data,
    if (fontFamily != null) 'fontFamily': fontFamily,
    if (fontWeight != null) 'fontWeight': fontWeight,
    if (italic) 'italic': true,
  };
}

final class ShareLayerConfig {
  ShareLayerConfig({
    required this.id,
    required this.label,
    required this.type,
    required this.zIndex,
    required this.transform,
    this.binding,
    this.defaultValue,
    this.visible = true,
    this.semanticRole = ShareSemanticRole.unassigned,
    this.emphasis = ShareLayerEmphasis.tertiary,
    this.runtimePermissions = const ShareLayerRuntimePermissions(),
    Map<String, Object?> style = const {},
    List<ShareControlConfig> controls = const [],
    this.access = const ShareAccessPolicy(),
    this.animation = const ShareAnimationSpec(),
  }) : style = Map<String, Object?>.unmodifiable(style),
       controls = List.unmodifiable(controls);

  factory ShareLayerConfig.fromJson(Map<String, dynamic> json) =>
      ShareLayerConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        type: _string(json, 'type'),
        zIndex: _int(json, 'zIndex'),
        transform: ShareLayerTransform.fromJson(_map(json, 'transform')),
        binding: json['binding'] as String?,
        defaultValue: json['defaultValue'],
        visible: json['visible'] as bool? ?? true,
        semanticRole: _enumValue(
          ShareSemanticRole.values,
          json['semanticRole'],
          'semantic role',
          fallback: ShareSemanticRole.unassigned,
        ),
        emphasis: _enumValue(
          ShareLayerEmphasis.values,
          json['emphasis'],
          'layer emphasis',
          fallback: ShareLayerEmphasis.tertiary,
        ),
        runtimePermissions: ShareLayerRuntimePermissions.fromJson(
          _mapOrNull(json['runtimePermissions']),
        ),
        style: Map<String, Object?>.from(_mapOrEmpty(json['style'])),
        controls:
            _list(
              json['controls'],
            ).map(_object).map(ShareControlConfig.fromJson).toList(),
        access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
        animation: ShareAnimationSpec.fromJson(_mapOrNull(json['animation'])),
      );

  final String id;
  final String label;
  final String type;
  final int zIndex;
  final ShareLayerTransform transform;
  final String? binding;
  final Object? defaultValue;
  final bool visible;
  final ShareSemanticRole semanticRole;
  final ShareLayerEmphasis emphasis;
  final ShareLayerRuntimePermissions runtimePermissions;
  final Map<String, Object?> style;
  final List<ShareControlConfig> controls;
  final ShareAccessPolicy access;
  final ShareAnimationSpec animation;

  ShareControlConfig? control(String id) {
    for (final control in controls) {
      if (control.id == id) return control;
    }
    return null;
  }

  ShareLayerConfig copyWith({
    String? id,
    String? label,
    String? type,
    int? zIndex,
    ShareLayerTransform? transform,
    String? binding,
    bool clearBinding = false,
    Object? defaultValue,
    bool? visible,
    ShareSemanticRole? semanticRole,
    ShareLayerEmphasis? emphasis,
    ShareLayerRuntimePermissions? runtimePermissions,
    Map<String, Object?>? style,
    List<ShareControlConfig>? controls,
    ShareAccessPolicy? access,
    ShareAnimationSpec? animation,
  }) => ShareLayerConfig(
    id: id ?? this.id,
    label: label ?? this.label,
    type: type ?? this.type,
    zIndex: zIndex ?? this.zIndex,
    transform: transform ?? this.transform,
    binding: clearBinding ? null : binding ?? this.binding,
    defaultValue: defaultValue ?? this.defaultValue,
    visible: visible ?? this.visible,
    semanticRole: semanticRole ?? this.semanticRole,
    emphasis: emphasis ?? this.emphasis,
    runtimePermissions: runtimePermissions ?? this.runtimePermissions,
    style: style ?? this.style,
    controls: controls ?? this.controls,
    access: access ?? this.access,
    animation: animation ?? this.animation,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'type': type,
    'zIndex': zIndex,
    'transform': transform.toJson(),
    if (binding != null) 'binding': binding,
    if (defaultValue != null) 'defaultValue': defaultValue,
    'visible': visible,
    'semanticRole': semanticRole.name,
    'emphasis': emphasis.name,
    'runtimePermissions': runtimePermissions.toJson(),
    'style': style,
    'controls': controls.map((item) => item.toJson()).toList(),
    'access': access.toJson(),
    'animation': animation.toJson(),
  };
}

final class ShareBackgroundConfig {
  ShareBackgroundConfig({
    required this.id,
    required this.label,
    required this.kind,
    Map<String, Object?> properties = const {},
    this.access = const ShareAccessPolicy(),
  }) : properties = Map<String, Object?>.unmodifiable(properties);

  factory ShareBackgroundConfig.fromJson(Map<String, dynamic> json) =>
      ShareBackgroundConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        kind: _string(json, 'kind'),
        properties: Map<String, Object?>.from(_mapOrEmpty(json['properties'])),
        access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
      );

  final String id;
  final String label;
  final String kind;
  final Map<String, Object?> properties;
  final ShareAccessPolicy access;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'kind': kind,
    'properties': properties,
    'access': access.toJson(),
  };
}

final class ShareStickerConfig {
  const ShareStickerConfig({
    required this.id,
    required this.label,
    required this.category,
    required this.assetId,
    required this.defaultScale,
    this.minimumScale = 0.1,
    this.maximumScale = 0.5,
    this.canMove = true,
    this.canResize = true,
    this.canRotate = true,
    this.canDelete = true,
    this.access = const ShareAccessPolicy(),
  });

  factory ShareStickerConfig.fromJson(Map<String, dynamic> json) =>
      ShareStickerConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        category: _string(json, 'category'),
        assetId: _string(json, 'assetId'),
        defaultScale: _double(json, 'defaultScale'),
        minimumScale: (json['minimumScale'] as num?)?.toDouble() ?? 0.1,
        maximumScale: (json['maximumScale'] as num?)?.toDouble() ?? 0.5,
        canMove: json['canMove'] as bool? ?? true,
        canResize: json['canResize'] as bool? ?? true,
        canRotate: json['canRotate'] as bool? ?? true,
        canDelete: json['canDelete'] as bool? ?? true,
        access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
      );

  final String id;
  final String label;
  final String category;
  final String assetId;
  final double defaultScale;
  final double minimumScale;
  final double maximumScale;
  final bool canMove;
  final bool canResize;
  final bool canRotate;
  final bool canDelete;
  final ShareAccessPolicy access;

  ShareStickerConfig copyWith({
    String? label,
    String? category,
    String? assetId,
    double? defaultScale,
    double? minimumScale,
    double? maximumScale,
    bool? canMove,
    bool? canResize,
    bool? canRotate,
    bool? canDelete,
    ShareAccessPolicy? access,
  }) => ShareStickerConfig(
    id: id,
    label: label ?? this.label,
    category: category ?? this.category,
    assetId: assetId ?? this.assetId,
    defaultScale: defaultScale ?? this.defaultScale,
    minimumScale: minimumScale ?? this.minimumScale,
    maximumScale: maximumScale ?? this.maximumScale,
    canMove: canMove ?? this.canMove,
    canResize: canResize ?? this.canResize,
    canRotate: canRotate ?? this.canRotate,
    canDelete: canDelete ?? this.canDelete,
    access: access ?? this.access,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'category': category,
    'assetId': assetId,
    'defaultScale': defaultScale,
    'minimumScale': minimumScale,
    'maximumScale': maximumScale,
    'canMove': canMove,
    'canResize': canResize,
    'canRotate': canRotate,
    'canDelete': canDelete,
    'access': access.toJson(),
  };
}

final class ShareLookConfig {
  ShareLookConfig({
    required this.id,
    required this.label,
    this.backgroundId,
    Map<String, Map<String, Object?>> layerOverrides = const {},
    List<ShareStickerValue> defaultStickers = const [],
    this.backgroundTreatment = const ShareBackgroundEdit(),
    this.editorVisible = true,
    this.access = const ShareAccessPolicy(),
  }) : layerOverrides = Map<String, Map<String, Object?>>.unmodifiable({
         for (final entry in layerOverrides.entries)
           entry.key: Map<String, Object?>.unmodifiable(entry.value),
       }),
       defaultStickers = List.unmodifiable(defaultStickers);

  factory ShareLookConfig.fromJson(Map<String, dynamic> json) =>
      ShareLookConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        backgroundId: json['backgroundId'] as String?,
        layerOverrides: _mapOrEmpty(json['layerOverrides']).map(
          (key, value) => MapEntry(
            key,
            Map<String, Object?>.from(value as Map<String, dynamic>),
          ),
        ),
        defaultStickers:
            _list(
              json['defaultStickers'],
            ).map(_object).map(ShareStickerValue.fromJson).toList(),
        backgroundTreatment:
            json['backgroundTreatment'] == null
                ? const ShareBackgroundEdit()
                : ShareBackgroundEdit.fromJson(
                  Map<String, dynamic>.from(json['backgroundTreatment'] as Map),
                ),
        editorVisible: json['editorVisible'] as bool? ?? true,
        access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
      );

  final String id;
  final String label;
  final String? backgroundId;
  final Map<String, Map<String, Object?>> layerOverrides;
  final List<ShareStickerValue> defaultStickers;
  final ShareBackgroundEdit backgroundTreatment;
  final bool editorVisible;
  final ShareAccessPolicy access;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    if (backgroundId != null) 'backgroundId': backgroundId,
    'layerOverrides': layerOverrides,
    'defaultStickers': defaultStickers.map((item) => item.toJson()).toList(),
    'backgroundTreatment': backgroundTreatment.toJson(),
    'editorVisible': editorVisible,
    'access': access.toJson(),
  };
}

final class ShareToolbarGroupConfig {
  const ShareToolbarGroupConfig({
    required this.id,
    required this.label,
    required this.icon,
    required this.order,
    this.access = const ShareAccessPolicy(),
  });

  factory ShareToolbarGroupConfig.fromJson(Map<String, dynamic> json) =>
      ShareToolbarGroupConfig(
        id: _string(json, 'id'),
        label: _string(json, 'label'),
        icon: _string(json, 'icon'),
        order: _int(json, 'order'),
        access: ShareAccessPolicy.fromJson(_mapOrNull(json['access'])),
      );

  final String id;
  final String label;
  final String icon;
  final int order;
  final ShareAccessPolicy access;

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'icon': icon,
    'order': order,
    'access': access.toJson(),
  };
}

final class ShareThemeConfig {
  ShareThemeConfig({
    required this.schemaVersion,
    required this.id,
    required this.name,
    required this.canvas,
    required List<ShareAssetConfig> assets,
    required List<ShareLayerConfig> layers,
    required List<ShareBackgroundConfig> backgrounds,
    required List<ShareStickerConfig> stickers,
    required List<ShareLookConfig> looks,
    required List<ShareTemplateConfig> templates,
    required List<ShareToolbarGroupConfig> toolbar,
    required this.defaultLookId,
    required this.defaultTemplateId,
    required this.defaultBackgroundId,
    required this.maximumStickerCount,
    required this.defaultToolbarGroupId,
    required this.designSystemVersion,
    int? maximumDecorationCount,
    this.premiumIcon = 'workspace_premium',
    this.sampleContent = const {},
  }) : maximumDecorationCount = maximumDecorationCount ?? maximumStickerCount,
       assets = List.unmodifiable(assets),
       layers = List.unmodifiable(
         <ShareLayerConfig>[...layers]..sort(_layerOrder),
       ),
       backgrounds = List.unmodifiable(backgrounds),
       stickers = List.unmodifiable(stickers),
       looks = List.unmodifiable(looks),
       templates = List.unmodifiable(templates),
       toolbar = List.unmodifiable(
         <ShareToolbarGroupConfig>[...toolbar]..sort(_toolbarOrder),
       ) {
    validate();
  }

  factory ShareThemeConfig.fromJson(Map<String, dynamic> json) {
    final source = _migrateThemeJson(json);
    return ShareThemeConfig(
      schemaVersion: _int(source, 'schemaVersion'),
      id: _string(source, 'id'),
      name: _string(source, 'name'),
      canvas: ShareCanvasConfig.fromJson(_map(source, 'canvas')),
      assets:
          _list(
            source['assets'],
          ).map(_object).map(ShareAssetConfig.fromJson).toList(),
      layers:
          _list(
            source['layers'],
          ).map(_object).map(ShareLayerConfig.fromJson).toList(),
      backgrounds:
          _list(
            source['backgrounds'],
          ).map(_object).map(ShareBackgroundConfig.fromJson).toList(),
      stickers:
          _list(
            source['stickers'],
          ).map(_object).map(ShareStickerConfig.fromJson).toList(),
      looks:
          _list(
            source['looks'],
          ).map(_object).map(ShareLookConfig.fromJson).toList(),
      templates:
          _list(
            source['templates'],
          ).map(_object).map(ShareTemplateConfig.fromJson).toList(),
      toolbar:
          _list(
            source['toolbar'],
          ).map(_object).map(ShareToolbarGroupConfig.fromJson).toList(),
      defaultLookId: _string(source, 'defaultLookId'),
      defaultTemplateId: _string(source, 'defaultTemplateId'),
      defaultBackgroundId: _string(source, 'defaultBackgroundId'),
      maximumStickerCount: _int(source, 'maximumStickerCount'),
      maximumDecorationCount:
          (source['maximumDecorationCount'] as num?)?.toInt(),
      defaultToolbarGroupId: _string(source, 'defaultToolbarGroupId'),
      designSystemVersion: _string(source, 'designSystemVersion'),
      premiumIcon: source['premiumIcon'] as String? ?? 'workspace_premium',
      sampleContent: Map<String, Object?>.from(
        _mapOrEmpty(source['sampleContent']),
      ),
    );
  }

  static const currentSchemaVersion = 3;
  static const supportedLayerTypes = {
    'background',
    'text',
    'image',
    'asset',
    'shape',
    'stickerWorkspace',
  };

  final int schemaVersion;
  final String id;
  final String name;
  final ShareCanvasConfig canvas;
  final List<ShareAssetConfig> assets;
  final List<ShareLayerConfig> layers;
  final List<ShareBackgroundConfig> backgrounds;
  final List<ShareStickerConfig> stickers;
  final List<ShareLookConfig> looks;
  final List<ShareTemplateConfig> templates;
  final List<ShareToolbarGroupConfig> toolbar;
  final String defaultLookId;
  final String defaultTemplateId;
  final String defaultBackgroundId;
  final int maximumStickerCount;
  final int maximumDecorationCount;
  final String defaultToolbarGroupId;
  final String designSystemVersion;
  final String premiumIcon;
  final Map<String, Object?> sampleContent;

  ShareLayerConfig layer(String id) => layers.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown layer'),
  );

  ShareAssetConfig asset(String id) => assets.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown asset'),
  );

  ShareBackgroundConfig background(String id) => backgrounds.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown background'),
  );

  ShareStickerConfig sticker(String id) => stickers.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown sticker'),
  );

  ShareLookConfig look(String id) => looks.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown look'),
  );

  ShareTemplateConfig template(String id) => templates.firstWhere(
    (item) => item.id == id,
    orElse: () => throw ArgumentError.value(id, 'id', 'Unknown template'),
  );

  void validate() {
    if (schemaVersion != currentSchemaVersion) {
      throw FormatException('Unsupported share theme schema: $schemaVersion');
    }
    if (id.trim().isEmpty || name.trim().isEmpty) {
      throw const FormatException('Theme ID and name cannot be empty');
    }
    if (canvas.width <= 0 ||
        canvas.height <= 0 ||
        canvas.outputWidth <= 0 ||
        canvas.outputHeight <= 0) {
      throw const FormatException('Canvas dimensions must be positive');
    }
    final logicalRatio = canvas.width / canvas.height;
    final outputRatio = canvas.outputWidth / canvas.outputHeight;
    if ((logicalRatio - outputRatio).abs() > 0.0001) {
      throw const FormatException(
        'Logical canvas and PNG output must have the same aspect ratio',
      );
    }
    if (canvas.safeInset < 0 ||
        canvas.safeInset * 2 >= canvas.width ||
        canvas.safeInset * 2 >= canvas.height) {
      throw const FormatException('Canvas safeInset is outside the canvas');
    }
    if (canvas.cornerRadius < 0 ||
        canvas.cornerRadius > canvas.width / 2 ||
        canvas.cornerRadius > canvas.height / 2) {
      throw const FormatException('Canvas cornerRadius is outside the canvas');
    }
    if (premiumIcon.trim().isEmpty) {
      throw const FormatException('premiumIcon cannot be empty');
    }
    if (designSystemVersion.trim().isEmpty) {
      throw const FormatException('designSystemVersion cannot be empty');
    }
    _unique(assets.map((item) => item.id), 'asset');
    _unique(layers.map((item) => item.id), 'layer');
    _unique(backgrounds.map((item) => item.id), 'background');
    _unique(stickers.map((item) => item.id), 'sticker');
    _unique(looks.map((item) => item.id), 'look');
    _unique(templates.map((item) => item.id), 'template');
    _unique(toolbar.map((item) => item.id), 'toolbar group');
    _unique(toolbar.map((item) => item.order.toString()), 'toolbar order');
    if (layers.isEmpty ||
        looks.isEmpty ||
        templates.isEmpty ||
        backgrounds.isEmpty) {
      throw const FormatException(
        'A theme requires layers, looks, templates, and backgrounds',
      );
    }
    look(defaultLookId);
    template(defaultTemplateId);
    background(defaultBackgroundId);
    if (maximumStickerCount < 0) {
      throw const FormatException('maximumStickerCount cannot be negative');
    }
    if (maximumDecorationCount < maximumStickerCount) {
      throw const FormatException(
        'maximumDecorationCount cannot be smaller than maximumStickerCount',
      );
    }
    if (!toolbar.any((item) => item.id == defaultToolbarGroupId)) {
      throw FormatException(
        'Unknown default toolbar group: $defaultToolbarGroupId',
      );
    }
    final assetIds = assets.map((item) => item.id).toSet();
    final assetsById = {for (final asset in assets) asset.id: asset};
    for (final asset in assets) {
      const supportedMimes = {
        'image/png',
        'image/jpeg',
        'image/webp',
        'font/ttf',
        'font/otf',
        'application/x-font-ttf',
        'application/x-font-opentype',
      };
      if (!{'image', 'font'}.contains(asset.kind)) {
        throw FormatException(
          'Asset ${asset.id} has invalid kind ${asset.kind}',
        );
      }
      if (!supportedMimes.contains(asset.mimeType.toLowerCase())) {
        throw FormatException(
          'Asset ${asset.id} has unsupported MIME type ${asset.mimeType}',
        );
      }
      if (asset.kind == 'font' &&
          (asset.fontFamily == null || asset.fontFamily!.trim().isEmpty)) {
        throw FormatException('Font asset ${asset.id} requires a fontFamily');
      }
      if ((asset.path == null || asset.path!.isEmpty) &&
          (asset.data == null || asset.data!.isEmpty)) {
        throw FormatException('Asset ${asset.id} requires path or data');
      }
      if (asset.data != null) {
        try {
          base64Decode(asset.data!);
        } on FormatException {
          throw FormatException('Asset ${asset.id} contains invalid base64');
        }
      }
    }
    for (final layer in layers) {
      _validateAnimation(layer.animation, 'Layer ${layer.id}');
      final rect = layer.transform;
      if (rect.width <= 0 || rect.height <= 0) {
        throw FormatException('Layer ${layer.id} has invalid dimensions');
      }
      if (rect.x < 0 ||
          rect.y < 0 ||
          rect.x + rect.width > canvas.width + 0.001 ||
          rect.y + rect.height > canvas.height + 0.001) {
        throw FormatException('Layer ${layer.id} is outside the canvas');
      }
      final binding = layer.binding;
      if (binding != null &&
          !ShareEditorContent.knownBindings.contains(binding) &&
          !binding.startsWith('custom.')) {
        throw FormatException('Layer ${layer.id} has unknown binding $binding');
      }
      _unique(layer.controls.map((item) => item.id), 'control in ${layer.id}');
      for (final control in layer.controls) {
        if (control.capability.trim().isEmpty) {
          throw FormatException('Control ${control.id} requires a capability');
        }
        if (control.minimum != null &&
            control.maximum != null &&
            control.minimum! > control.maximum!) {
          throw FormatException('Control ${control.id} has an invalid range');
        }
        if (control.kind == ShareControlKind.choice &&
            control.options.isEmpty) {
          throw FormatException('Choice control ${control.id} needs options');
        }
        if (control.defaultValue is num) {
          final value = (control.defaultValue! as num).toDouble();
          if ((control.minimum != null && value < control.minimum!) ||
              (control.maximum != null && value > control.maximum!)) {
            throw FormatException(
              'Control ${control.id} default is outside its range',
            );
          }
        }
        if (control.kind == ShareControlKind.choice &&
            control.defaultValue != null &&
            !control.options.contains('${control.defaultValue}')) {
          throw FormatException(
            'Control ${control.id} default is not an allowed option',
          );
        }
      }
      final assetId = layer.style['assetId'] as String?;
      if (assetId != null && !assetIds.contains(assetId)) {
        throw FormatException('Layer ${layer.id} uses missing asset $assetId');
      }
      if (assetId != null && assetsById[assetId]!.kind != 'image') {
        throw FormatException('Layer ${layer.id} requires an image asset');
      }
      final fallbackAssetId = layer.style['fallbackAssetId'] as String?;
      if (fallbackAssetId != null && !assetIds.contains(fallbackAssetId)) {
        throw FormatException(
          'Layer ${layer.id} uses missing fallback asset $fallbackAssetId',
        );
      }
    }
    for (final item in backgrounds) {
      _validateBackground(item, assetsById);
    }
    for (final item in stickers) {
      if (!assetIds.contains(item.assetId)) {
        throw FormatException(
          'Sticker ${item.id} uses missing asset ${item.assetId}',
        );
      }
      if (assetsById[item.assetId]!.kind != 'image') {
        throw FormatException('Sticker ${item.id} requires an image asset');
      }
      if (item.minimumScale <= 0 ||
          item.maximumScale < item.minimumScale ||
          item.defaultScale < item.minimumScale ||
          item.defaultScale > item.maximumScale) {
        throw FormatException('Sticker ${item.id} has an invalid scale range');
      }
    }
    if (stickers.isNotEmpty &&
        !layers.any((layer) => layer.type == 'stickerWorkspace')) {
      throw const FormatException(
        'A sticker catalog requires a stickerWorkspace layer',
      );
    }
    final layerIds = layers.map((item) => item.id).toSet();
    final backgroundIds = backgrounds.map((item) => item.id).toSet();
    final stickerIds = stickers.map((item) => item.id).toSet();
    for (final item in looks) {
      _validateBackgroundEdit(item.backgroundTreatment, 'Look ${item.id}');
      if (item.backgroundId != null &&
          !backgroundIds.contains(item.backgroundId)) {
        throw FormatException(
          'Look ${item.id} uses missing background ${item.backgroundId}',
        );
      }
      for (final layerId in item.layerOverrides.keys) {
        if (!layerIds.contains(layerId)) {
          throw FormatException(
            'Look ${item.id} overrides missing layer $layerId',
          );
        }
        final override = item.layerOverrides[layerId]!;
        final transform = override['transform'];
        if (transform != null) {
          if (transform is! Map<String, dynamic>) {
            throw FormatException(
              'Look ${item.id} layer $layerId has an invalid transform',
            );
          }
          final rect = ShareLayerTransform.fromJson(transform);
          if (rect.width <= 0 ||
              rect.height <= 0 ||
              rect.x < 0 ||
              rect.y < 0 ||
              rect.x + rect.width > canvas.width + 0.001 ||
              rect.y + rect.height > canvas.height + 0.001) {
            throw FormatException(
              'Look ${item.id} layer $layerId is outside the canvas',
            );
          }
        }
      }
      _unique(
        item.defaultStickers.map((sticker) => sticker.instanceId),
        'default sticker instance in ${item.id}',
      );
      for (final stickerValue in item.defaultStickers) {
        if (!stickerIds.contains(stickerValue.stickerId)) {
          throw FormatException(
            'Look ${item.id} uses missing sticker ${stickerValue.stickerId}',
          );
        }
        final config = stickers.firstWhere(
          (sticker) => sticker.id == stickerValue.stickerId,
        );
        if (stickerValue.centerX < 0 ||
            stickerValue.centerX > 1 ||
            stickerValue.centerY < 0 ||
            stickerValue.centerY > 1 ||
            stickerValue.scale < config.minimumScale ||
            stickerValue.scale > config.maximumScale) {
          throw FormatException(
            'Look ${item.id} has invalid default sticker ${stickerValue.instanceId}',
          );
        }
      }
    }
    for (final item in templates) {
      _validateAnimation(item.animation, 'Template ${item.id}');
      if (item.accentColorToken.trim().isEmpty) {
        throw FormatException('Template ${item.id} requires an accent token');
      }
      if (item.mediaCoverage < 0 || item.mediaCoverage > 1) {
        throw FormatException(
          'Template ${item.id} has invalid media coverage',
        );
      }
      if (item.variant.trim().isEmpty || item.narrativeIntent.trim().isEmpty) {
        throw FormatException(
          'Template ${item.id} requires variant and narrative intent',
        );
      }
      if (item.templateVersion < 1 || item.supportedMediaCount < 0) {
        throw FormatException('Template ${item.id} has invalid version/media');
      }
      if (item.designSystemVersion != designSystemVersion) {
        throw FormatException(
          'Template ${item.id} targets ${item.designSystemVersion}, expected $designSystemVersion',
        );
      }
      if (item.requiredContentRoles
          .intersection(item.optionalContentRoles)
          .isNotEmpty) {
        throw FormatException(
          'Template ${item.id} has roles that are both required and optional',
        );
      }
      if (item.supportedJourneyStates.isNotEmpty &&
          !item.supportedJourneyStates.contains(item.primaryJourneyState)) {
        throw FormatException(
          'Template ${item.id} primary journey state is not supported',
        );
      }
      for (final layerId in item.layerOverrides.keys) {
        if (!layerIds.contains(layerId)) {
          throw FormatException(
            'Template ${item.id} overrides missing layer $layerId',
          );
        }
        final transform = item.layerOverrides[layerId]!['transform'];
        if (transform != null) {
          if (transform is! Map<String, dynamic>) {
            throw FormatException(
              'Template ${item.id} layer $layerId has an invalid transform',
            );
          }
          final rect = ShareLayerTransform.fromJson(transform);
          _validateRect(rect, canvas, 'Template ${item.id} layer $layerId');
        }
      }
      _unique(item.safeZones.map((zone) => zone.id), 'safe zone in ${item.id}');
      for (final zone in item.safeZones) {
        _validateRect(zone.rect, canvas, 'Safe zone ${zone.id}');
      }
    }
  }

  Map<String, dynamic> toJson() => {
    'schemaVersion': schemaVersion,
    'id': id,
    'name': name,
    'canvas': canvas.toJson(),
    'assets': assets.map((item) => item.toJson()).toList(),
    'layers': layers.map((item) => item.toJson()).toList(),
    'backgrounds': backgrounds.map((item) => item.toJson()).toList(),
    'stickers': stickers.map((item) => item.toJson()).toList(),
    'looks': looks.map((item) => item.toJson()).toList(),
    'templates': templates.map((item) => item.toJson()).toList(),
    'toolbar': toolbar.map((item) => item.toJson()).toList(),
    'defaultLookId': defaultLookId,
    'defaultTemplateId': defaultTemplateId,
    'defaultBackgroundId': defaultBackgroundId,
    'maximumStickerCount': maximumStickerCount,
    'maximumDecorationCount': maximumDecorationCount,
    'defaultToolbarGroupId': defaultToolbarGroupId,
    'designSystemVersion': designSystemVersion,
    'premiumIcon': premiumIcon,
    'sampleContent': sampleContent,
  };

  static int _layerOrder(ShareLayerConfig a, ShareLayerConfig b) =>
      a.zIndex.compareTo(b.zIndex);
  static int _toolbarOrder(
    ShareToolbarGroupConfig a,
    ShareToolbarGroupConfig b,
  ) => a.order.compareTo(b.order);
}

abstract final class ShareThemeBundle {
  static const defaultAsset =
      'lib/generated_share_editor/config/share_theme.json';
  static ShareThemeConfig? _cachedDefault;

  static Future<ShareThemeConfig> loadAsset({
    String path = defaultAsset,
    Object? bundle,
  }) async {
    if (bundle == null && path == defaultAsset && _cachedDefault != null) {
      return _cachedDefault!;
    }
    final raw = await asset_loader.loadShareThemeAsset(path, bundle);
    final theme = fromJsonString(raw);
    if (bundle == null && path == defaultAsset) _cachedDefault = theme;
    return theme;
  }

  static ShareThemeConfig fromJsonString(String raw) {
    final decoded = jsonDecode(raw);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Share theme must be a JSON object');
    }
    return ShareThemeConfig.fromJson(decoded);
  }

  static String toJsonString(ShareThemeConfig theme, {bool pretty = true}) =>
      (pretty ? const JsonEncoder.withIndent('  ') : const JsonEncoder())
          .convert(theme.toJson());
}

void _validateBackground(
  ShareBackgroundConfig item,
  Map<String, ShareAssetConfig> assetsById,
) {
  const supported = {'solid', 'image', 'linear', 'radial', 'sweep'};
  if (!supported.contains(item.kind)) {
    throw FormatException(
      'Background ${item.id} has unknown kind ${item.kind}',
    );
  }
  if (item.kind == 'solid' && !_isColor(item.properties['color'])) {
    throw FormatException('Background ${item.id} has an invalid solid color');
  }
  if (item.kind == 'image') {
    final assetId = item.properties['assetId'] as String?;
    final binding = item.properties['binding'] as String?;
    if (assetId == null && binding == null) {
      throw FormatException('Image background ${item.id} needs an asset');
    }
    if (assetId != null && !assetsById.containsKey(assetId)) {
      throw FormatException(
        'Background ${item.id} uses missing asset $assetId',
      );
    }
    if (assetId != null && assetsById[assetId]!.kind != 'image') {
      throw FormatException('Background ${item.id} requires an image asset');
    }
    final fallbackAssetId = item.properties['fallbackAssetId'] as String?;
    if (fallbackAssetId != null && !assetsById.containsKey(fallbackAssetId)) {
      throw FormatException(
        'Background ${item.id} uses missing fallback asset $fallbackAssetId',
      );
    }
    if (binding != null &&
        !ShareEditorContent.knownBindings.contains(binding) &&
        !binding.startsWith('custom.')) {
      throw FormatException(
        'Background ${item.id} has unknown binding $binding',
      );
    }
    final overlay = item.properties['overlayColor'];
    if (overlay != null && !_isColor(overlay)) {
      throw FormatException('Background ${item.id} has invalid overlay color');
    }
  }
  if ({'linear', 'radial', 'sweep'}.contains(item.kind)) {
    final colors = _list(item.properties['colors']);
    final stops = _list(item.properties['stops']);
    if (colors.length < 2 ||
        (stops.isNotEmpty && stops.length != colors.length)) {
      throw FormatException('Gradient ${item.id} has invalid colors or stops');
    }
    for (final color in colors) {
      if (!_isColor(color)) {
        throw FormatException('Gradient ${item.id} has invalid color $color');
      }
    }
    var previous = -1.0;
    for (final stop in stops) {
      if (stop is! num) {
        throw FormatException('Gradient ${item.id} has a non-numeric stop');
      }
      final value = stop.toDouble();
      if (value < 0 || value > 1 || value < previous) {
        throw FormatException('Gradient ${item.id} has invalid stops');
      }
      previous = value;
    }
    final opacity = item.properties['opacity'];
    if (opacity != null &&
        (opacity is! num || opacity.toDouble() < 0 || opacity.toDouble() > 1)) {
      throw FormatException('Gradient ${item.id} has invalid opacity');
    }
    final tileMode = item.properties['tileMode'];
    if (tileMode != null &&
        !{'clamp', 'repeat', 'mirror', 'decal'}.contains(tileMode)) {
      throw FormatException('Gradient ${item.id} has invalid tile mode');
    }
    if (item.kind == 'radial' &&
        _numberOrNull(item.properties['radius']) != null &&
        _numberOrNull(item.properties['radius'])! <= 0) {
      throw FormatException('Gradient ${item.id} has invalid radius');
    }
    if (item.kind == 'sweep') {
      final start = _numberOrNull(item.properties['startAngle']);
      final end = _numberOrNull(item.properties['endAngle']);
      if (start != null && end != null && end <= start) {
        throw FormatException('Gradient ${item.id} has invalid sweep angles');
      }
    }
  }
}

void _validateBackgroundEdit(ShareBackgroundEdit edit, String label) {
  bool within(double value, double minimum, double maximum) =>
      value.isFinite && value >= minimum && value <= maximum;
  if (!within(edit.alignmentX, -1, 1) ||
      !within(edit.alignmentY, -1, 1) ||
      !within(edit.zoom, 1, 4) ||
      !within(edit.imageOpacity, 0.2, 1) ||
      !within(edit.blur, 0, 30) ||
      !within(edit.brightness, -1, 1) ||
      !within(edit.contrast, 0.5, 2) ||
      !within(edit.saturation, 0, 2) ||
      !within(edit.tintOpacity, 0, 1) ||
      !within(edit.overlayOpacity, 0, 1) ||
      !within(edit.textureIntensity, 0, 1) ||
      !within(edit.textureScale, 0.5, 4)) {
    throw FormatException('$label has an invalid background treatment');
  }
  for (final color in [
    edit.tintColor,
    edit.overlayColor,
    edit.textureColor,
    edit.textureSecondaryColor,
  ]) {
    if (!_isColor(color)) {
      throw FormatException('$label has an invalid background color');
    }
  }
}

double? _numberOrNull(Object? value) => value is num ? value.toDouble() : null;

Map<String, dynamic> _migrateThemeJson(Map<String, dynamic> json) {
  final version = json['schemaVersion'];
  if (version == ShareThemeConfig.currentSchemaVersion) return json;
  if (version != 1 && version != 2) {
    throw FormatException('Unsupported share theme schema: $version');
  }

  final migrated = jsonDecode(jsonEncode(json)) as Map<String, dynamic>;
  const designSystemVersion = 'ptw_ds_v1';
  migrated['schemaVersion'] = ShareThemeConfig.currentSchemaVersion;
  migrated['designSystemVersion'] = designSystemVersion;

  if (version == 1) {
    final legacyPermissions =
        const ShareLayerRuntimePermissions(
          canEditContent: true,
          canReplaceMedia: true,
          canCropMedia: true,
          canMove: true,
          canResize: true,
          canRotate: true,
          canStyle: true,
          canHide: true,
        ).toJson();
    for (final rawLayer in _list(migrated['layers'])) {
      final layer = _object(rawLayer);
      layer['semanticRole'] ??= ShareSemanticRole.unassigned.name;
      layer['emphasis'] ??= ShareLayerEmphasis.tertiary.name;
      layer['runtimePermissions'] ??= legacyPermissions;
    }

    const legacyTemplateId = 'legacy_default';
    migrated['templates'] = [
      {
        'id': legacyTemplateId,
        'label': 'Legacy template',
        'family': ShareTemplateFamily.unassigned.name,
        'variant': 'legacy',
        'narrativeIntent': 'Preserve an imported schema v1 composition.',
        'primaryJourneyState': ShareJourneyState.unassigned.name,
        'supportedJourneyStates': [ShareJourneyState.unassigned.name],
        'requiredContentRoles': <String>[],
        'optionalContentRoles': <String>[],
        'runtimePermissions':
            const ShareTemplateRuntimePermissions(
              userCanReplaceMedia: true,
              userCanCropMedia: true,
              userCanEditHeadline: true,
              userCanEditProofValue: true,
              userCanChooseAlternateTemplate: true,
              userCanHideOptionalNote: true,
              userCanEditDecorations: true,
            ).toJson(),
        'primaryAnchor': ShareSemanticRole.unassigned.name,
        'supportedMediaCount': 1,
        'supportsComparison': false,
        'supportsProof': false,
        'safeZones': <Object?>[],
        'designSystemVersion': designSystemVersion,
        'templateVersion': 1,
        'status': ShareTemplateStatus.experimental.name,
        'layerOverrides': <String, Object?>{},
      },
    ];
    migrated['defaultTemplateId'] = legacyTemplateId;
  }

  for (final rawLayer in _list(migrated['layers'])) {
    final layer = _object(rawLayer);
    layer['animation'] ??= const ShareAnimationSpec().toJson();
  }
  for (final rawTemplate in _list(migrated['templates'])) {
    final template = _object(rawTemplate);
    template['animation'] ??= const ShareAnimationSpec().toJson();
  }
  return migrated;
}

ShareJourneyState _journeyState(Object? raw, String label) {
  final canonical = switch (raw) {
    'grind' => 'grinding',
    'setback' => 'failure',
    'result' => 'finish',
    _ => raw,
  };
  return _enumValue(ShareJourneyState.values, canonical, label);
}

Set<ShareJourneyState> _journeyStateSet(Object? raw, String label) {
  final values = _list(raw);
  return {for (final value in values) _journeyState(value, label)};
}

T _enumValue<T extends Enum>(
  List<T> values,
  Object? raw,
  String label, {
  T? fallback,
}) {
  if (raw == null && fallback != null) return fallback;
  if (raw is String) {
    for (final value in values) {
      if (value.name == raw) return value;
    }
  }
  throw FormatException('Unknown $label: $raw');
}

Set<T> _enumSet<T extends Enum>(List<T> values, Object? raw, String label) {
  final result = <T>{};
  for (final item in _list(raw)) {
    result.add(_enumValue(values, item, label));
  }
  return result;
}

void _validateRect(
  ShareLayerTransform rect,
  ShareCanvasConfig canvas,
  String label,
) {
  if (rect.width <= 0 ||
      rect.height <= 0 ||
      rect.x < 0 ||
      rect.y < 0 ||
      rect.x + rect.width > canvas.width + 0.001 ||
      rect.y + rect.height > canvas.height + 0.001) {
    throw FormatException('$label is outside the canvas');
  }
}

void _validateAnimation(ShareAnimationSpec animation, String owner) {
  if (animation.delayMilliseconds < 0 ||
      animation.durationMilliseconds <= 0 ||
      animation.easing.trim().isEmpty) {
    throw FormatException('$owner has invalid animation metadata');
  }
}

bool _isColor(Object? value) {
  if (value is int) return value >= 0 && value <= 0xffffffff;
  if (value is! String) return false;
  return RegExp(r'^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$').hasMatch(value);
}

void _unique(Iterable<String> values, String label) {
  final list = values.toList();
  if (list.toSet().length != list.length || list.any((item) => item.isEmpty)) {
    throw FormatException(
      '${label[0].toUpperCase()}${label.substring(1)} IDs must be non-empty and unique',
    );
  }
}

String _string(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('$key must be a non-empty string');
  }
  return value;
}

int _int(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) throw FormatException('$key must be an integer');
  return value;
}

double _double(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) throw FormatException('$key must be a number');
  return value.toDouble();
}

Map<String, dynamic> _map(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! Map<String, dynamic>) {
    throw FormatException('$key must be an object');
  }
  return value;
}

Map<String, dynamic>? _mapOrNull(Object? value) =>
    value == null ? null : _object(value);

Map<String, dynamic> _mapOrEmpty(Object? value) =>
    value == null ? <String, dynamic>{} : _object(value);

Map<String, dynamic> _object(Object? value) {
  if (value is! Map<String, dynamic>) {
    throw const FormatException('Expected an object');
  }
  return value;
}

List<dynamic> _list(Object? value) {
  if (value == null) return const [];
  if (value is! List<dynamic>) throw const FormatException('Expected a list');
  return value;
}
