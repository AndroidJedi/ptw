import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import 'share_theme.dart';
import 'share_value.dart';

typedef ShareEntitlementResolver = bool Function(String entitlementKey);

enum ShareAccessState { available, locked, hidden }

/// Authoring exposes the complete theme surface. Runtime only exposes the
/// choices explicitly granted by the active template and layer.
enum ShareEditorMode { authoring, runtime }

final class ShareLockedFeature {
  const ShareLockedFeature({
    required this.id,
    required this.label,
    required this.entitlementKey,
  });

  final String id;
  final String label;
  final String entitlementKey;
}

final class ShareEditorController extends ChangeNotifier {
  factory ShareEditorController({
    required ShareThemeConfig theme,
    required ShareEditorContent content,
    ShareEditorValue? initialValue,
    ShareEntitlementResolver? entitlements,
    ShareEditorMode mode = ShareEditorMode.authoring,
    bool allowRuntimeTemplateSelection = false,
  }) {
    final validated = _validatedInitial(theme, content, initialValue);
    return ShareEditorController._(
      theme: theme,
      content: content,
      initial: validated,
      entitlements: entitlements ?? _denyEntitlements,
      mode: mode,
      allowRuntimeTemplateSelection: allowRuntimeTemplateSelection,
    );
  }

  ShareEditorController._({
    required this.theme,
    required this.content,
    required ShareEditorValue initial,
    required ShareEntitlementResolver entitlements,
    required this.mode,
    required this.allowRuntimeTemplateSelection,
  }) : _entitlements = entitlements,
       _initial = initial,
       _value = initial {
    _nextSticker = initial.stickers.length + 1;
    _nextOverlay = initial.overlays.length + 1;
  }

  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final ShareEntitlementResolver _entitlements;
  final ShareEditorMode mode;
  final bool allowRuntimeTemplateSelection;
  final ShareEditorValue _initial;
  ShareEditorValue _value;
  int _nextSticker = 1;
  int _nextOverlay = 1;
  String? _selectedLayerId;
  String? _selectedStickerId;
  String? _selectedOverlayId;
  bool _hasChanges = false;

  ShareEditorValue get value => _value;
  bool get hasChanges => _hasChanges;
  String? get selectedLayerId => _selectedLayerId;
  String? get selectedStickerId => _selectedStickerId;
  String? get selectedOverlayId => _selectedOverlayId;
  int get decorationCount => _value.stickers.length + _value.overlays.length;
  bool get canAddDecoration => decorationCount < theme.maximumDecorationCount;
  bool get canAddSticker =>
      canAddDecoration && _value.stickers.length < theme.maximumStickerCount;

  static const minimumOverlayScale = 0.08;
  static const maximumOverlayScale = 0.65;

  ShareLookConfig get activeLook => theme.look(_value.lookId);
  ShareTemplateConfig get activeTemplate =>
      theme.template(_value.templateId ?? theme.defaultTemplateId);

  ShareLayerConfig effectiveLayer(String layerId) {
    final base = theme.layer(layerId);
    final structured = _mergeLayerOverride(
      base,
      activeTemplate.layerOverrides[layerId],
    );
    return _mergeLayerOverride(structured, activeLook.layerOverrides[layerId]);
  }

  ShareLayerConfig _mergeLayerOverride(
    ShareLayerConfig base,
    Map<String, Object?>? override,
  ) {
    if (override == null) return base;
    final styleOverride = override['style'];
    final mergedStyle = <String, Object?>{
      ...base.style,
      if (styleOverride is Map<String, dynamic>) ...styleOverride,
      if (styleOverride is Map<String, Object?>) ...styleOverride,
    };
    final rawTransform = override['transform'];
    final rawEmphasis = override['emphasis'];
    return base.copyWith(
      visible: override['visible'] as bool?,
      defaultValue: override['defaultValue'],
      transform:
          rawTransform is Map<String, dynamic>
              ? ShareLayerTransform.fromJson(rawTransform)
              : base.transform,
      style: mergedStyle,
      emphasis:
          rawEmphasis is String
              ? ShareLayerEmphasis.values.firstWhere(
                (item) => item.name == rawEmphasis,
                orElse: () => base.emphasis,
              )
              : base.emphasis,
    );
  }

  ShareLayerTransform effectiveTransform(String layerId) =>
      _value.transforms[layerId] ?? effectiveLayer(layerId).transform;

  Map<String, Object?> effectiveStyle(String layerId) => {
    ...effectiveLayer(layerId).style,
    ...?_value.propertyOverrides[layerId],
  };

  Object? layerValue(String layerId) {
    final layer = effectiveLayer(layerId);
    return _value.layerValues[layerId] ??
        (layer.binding == null ? null : content.resolve(layer.binding!)) ??
        layer.defaultValue;
  }

  ShareAccessState accessState(ShareAccessPolicy policy) {
    if (policy.mode == ShareAccessMode.free ||
        _entitlements(policy.entitlementKey!)) {
      return ShareAccessState.available;
    }
    return policy.mode == ShareAccessMode.premiumHidden
        ? ShareAccessState.hidden
        : ShareAccessState.locked;
  }

  bool canAccess(ShareAccessPolicy policy) =>
      accessState(policy) == ShareAccessState.available;

  ShareAccessState controlAccess(String layerId, String controlId) {
    final control = theme.layer(layerId).control(controlId);
    if (control == null ||
        !_runtimeAllows(theme.layer(layerId), control.capability)) {
      return ShareAccessState.hidden;
    }
    return accessState(control.access);
  }

  bool canUseControl(String layerId, String capability) =>
      _allowed(theme.layer(layerId), capability);

  ShareLockedFeature lockedFeature({
    required String id,
    required String label,
    required ShareAccessPolicy access,
  }) => ShareLockedFeature(
    id: id,
    label: label,
    entitlementKey: access.entitlementKey ?? 'premium',
  );

  void selectLayer(String? layerId) {
    if (layerId != null) theme.layer(layerId);
    _selectedLayerId = layerId;
    _selectedStickerId = null;
    _selectedOverlayId = null;
    notifyListeners();
  }

  void selectSticker(String? instanceId) {
    if (instanceId != null &&
        !_value.stickers.any((item) => item.instanceId == instanceId)) {
      return;
    }
    _selectedStickerId = instanceId;
    _selectedLayerId = null;
    _selectedOverlayId = null;
    notifyListeners();
  }

  void selectOverlay(String? instanceId) {
    if (instanceId != null &&
        !_value.overlays.any((item) => item.instanceId == instanceId)) {
      return;
    }
    _selectedOverlayId = instanceId;
    _selectedStickerId = null;
    _selectedLayerId = null;
    notifyListeners();
  }

  bool updateLayerValue(String layerId, Object? value) {
    final layer = theme.layer(layerId);
    if (!_allowed(layer, 'edit')) return false;
    _value = _value.copyWith(
      layerValues: {..._value.layerValues, layerId: value},
    );
    _changed();
    return true;
  }

  bool updateLayerProperty(String layerId, String property, Object? value) {
    return updateLayerProperties(layerId, {property: value});
  }

  bool updateLayerProperties(String layerId, Map<String, Object?> properties) {
    final layer = theme.layer(layerId);
    final safeProperties = <String, Object?>{};
    for (final entry in properties.entries) {
      final control = layer.control(entry.key);
      if (control == null ||
          !canAccess(control.access) ||
          !_runtimeAllows(layer, control.capability)) {
        return false;
      }
      Object? safe = entry.value;
      if (safe is num) {
        safe = safe.toDouble().clamp(
          control.minimum ?? -double.maxFinite,
          control.maximum ?? double.maxFinite,
        );
      }
      if (control.options.isNotEmpty && !control.options.contains('$safe')) {
        return false;
      }
      safeProperties[entry.key] = safe;
    }
    final overrides = <String, Map<String, Object?>>{
      ..._value.propertyOverrides,
      layerId: {...?_value.propertyOverrides[layerId], ...safeProperties},
    };
    _value = _value.copyWith(propertyOverrides: overrides);
    _changed();
    return true;
  }

  bool updateLayerTransform(
    String layerId, {
    double? x,
    double? y,
    double? width,
    double? height,
    double? rotation,
  }) {
    final layer = theme.layer(layerId);
    final current = effectiveTransform(layerId);
    final moves = x != null || y != null;
    final resizes = width != null || height != null;
    if (moves && !_allowed(layer, 'move')) return false;
    if (resizes && !_allowed(layer, 'resize')) return false;
    if (rotation != null && !_allowed(layer, 'rotate')) return false;
    final nextWidth = (width ?? current.width).clamp(1.0, theme.canvas.width);
    final nextHeight = (height ?? current.height).clamp(
      1.0,
      theme.canvas.height,
    );
    final next = current.copyWith(
      x: (x ?? current.x).clamp(0, theme.canvas.width - nextWidth),
      y: (y ?? current.y).clamp(0, theme.canvas.height - nextHeight),
      width: nextWidth,
      height: nextHeight,
      rotation: rotation == null ? null : _normalize(rotation),
    );
    _value = _value.copyWith(transforms: {..._value.transforms, layerId: next});
    _changed();
    return true;
  }

  bool selectBackground(String backgroundId) {
    if (mode == ShareEditorMode.runtime) return false;
    final background = theme.background(backgroundId);
    if (!canAccess(background.access)) return false;
    _value = _value.copyWith(backgroundId: backgroundId);
    _changed();
    return true;
  }

  bool updateBackground(ShareBackgroundEdit value) {
    if (mode == ShareEditorMode.runtime) return false;
    final safe = _validatedBackgroundEdit(value);
    _value = _value.copyWith(backgroundEdit: safe);
    _changed();
    return true;
  }

  bool replaceBackgroundImage(ShareImageValue image) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanReplaceMedia) {
      return false;
    }
    final safe = _validatedBackgroundEdit(
      _value.backgroundEdit.copyWith(
        image: image,
        alignmentX: 0,
        alignmentY: 0,
        zoom: 1,
      ),
    );
    _value = _value.copyWith(backgroundEdit: safe);
    _changed();
    return true;
  }

  bool useProjectBackground() {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanReplaceMedia) {
      return false;
    }
    final safe = _validatedBackgroundEdit(
      _value.backgroundEdit.copyWith(
        clearImage: true,
        alignmentX: 0,
        alignmentY: 0,
        zoom: 1,
      ),
    );
    _value = _value.copyWith(backgroundEdit: safe);
    _changed();
    return true;
  }

  bool updateBackgroundCrop({
    double? alignmentX,
    double? alignmentY,
    double? zoom,
  }) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanCropMedia) {
      return false;
    }
    final safe = _validatedBackgroundEdit(
      _value.backgroundEdit.copyWith(
        alignmentX: alignmentX,
        alignmentY: alignmentY,
        zoom: zoom,
      ),
    );
    _value = _value.copyWith(backgroundEdit: safe);
    _changed();
    return true;
  }

  bool selectLook(String lookId) {
    if (mode == ShareEditorMode.runtime) return false;
    final look = theme.look(lookId);
    if (!canAccess(look.access)) return false;
    final currentBackground = _value.backgroundEdit;
    final treatment = look.backgroundTreatment.copyWith(
      image: currentBackground.image,
      clearImage: currentBackground.image == null,
      alignmentX: currentBackground.alignmentX,
      alignmentY: currentBackground.alignmentY,
      zoom: currentBackground.zoom,
    );
    _value = _value.copyWith(
      lookId: look.id,
      backgroundId: look.backgroundId ?? _value.backgroundId,
      backgroundEdit: treatment,
      stickers: look.defaultStickers,
      transforms: const {},
      propertyOverrides: const {},
    );
    _selectedLayerId = null;
    _selectedStickerId = null;
    _selectedOverlayId = null;
    _nextSticker = 1;
    _changed();
    return true;
  }

  bool cycleLook() {
    if (mode == ShareEditorMode.runtime) return false;
    final visible =
        theme.looks
            .where(
              (item) =>
                  item.editorVisible &&
                  accessState(item.access) != ShareAccessState.hidden,
            )
            .toList();
    if (visible.isEmpty) return false;
    final current = visible.indexWhere((item) => item.id == _value.lookId);
    for (var offset = 1; offset <= visible.length; offset++) {
      final candidate =
          visible[(math.max(0, current) + offset) % visible.length];
      if (canAccess(candidate.access)) return selectLook(candidate.id);
    }
    return false;
  }

  bool selectTemplate(String templateId) {
    final template = theme.template(templateId);
    if (mode == ShareEditorMode.runtime &&
        !allowRuntimeTemplateSelection &&
        !activeTemplate.runtimePermissions.userCanChooseAlternateTemplate) {
      return false;
    }
    if (template.id == activeTemplate.id) return true;
    _value = _value.copyWith(
      templateId: template.id,
      transforms: const {},
      propertyOverrides: const {},
    );
    _selectedLayerId = null;
    _selectedStickerId = null;
    _selectedOverlayId = null;
    _changed();
    return true;
  }

  bool cycleTemplate() {
    if (theme.templates.isEmpty) return false;
    final current = theme.templates.indexWhere(
      (item) => item.id == activeTemplate.id,
    );
    for (var offset = 1; offset <= theme.templates.length; offset++) {
      final candidate =
          theme.templates[(math.max(0, current) + offset) %
              theme.templates.length];
      if (selectTemplate(candidate.id)) return true;
    }
    return false;
  }

  bool addSticker(String stickerId) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    if (!canAddSticker) return false;
    final sticker = theme.sticker(stickerId);
    if (!canAccess(sticker.access)) return false;
    final workspace = _workspace;
    if (workspace != null && !_allowed(workspace, 'add')) return false;
    final index = _value.stickers.length;
    const anchors = [(0.76, 0.24), (0.24, 0.72), (0.76, 0.72)];
    final anchor = anchors[index % anchors.length];
    final value = ShareStickerValue(
      instanceId: '${sticker.id}_${_nextSticker++}',
      stickerId: sticker.id,
      centerX: anchor.$1,
      centerY: anchor.$2,
      scale: sticker.defaultScale,
      rotation: 0,
    );
    _value = _value.copyWith(stickers: [..._value.stickers, value]);
    _selectedLayerId = null;
    _selectedStickerId = value.instanceId;
    _selectedOverlayId = null;
    _changed();
    return true;
  }

  bool addOverlay(ShareImageValue image) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    if (!canAddDecoration) return false;
    final index = decorationCount;
    const anchors = [(0.78, 0.26), (0.22, 0.72), (0.78, 0.74)];
    final anchor = anchors[index % anchors.length];
    final value = SharePlacedOverlayValue(
      instanceId: 'upload_${_nextOverlay++}',
      image: image,
      centerX: anchor.$1,
      centerY: anchor.$2,
      scale: 0.24,
      rotation: 0,
    );
    _value = _value.copyWith(overlays: [..._value.overlays, value]);
    _selectedLayerId = null;
    _selectedStickerId = null;
    _selectedOverlayId = value.instanceId;
    _changed();
    return true;
  }

  bool updateOverlay(
    String instanceId, {
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    final index = _value.overlays.indexWhere(
      (item) => item.instanceId == instanceId,
    );
    if (index < 0) return false;
    final current = _value.overlays[index];
    final updated = current.copyWith(
      centerX: centerX?.clamp(0.02, 0.98),
      centerY: centerY?.clamp(0.02, 0.98),
      scale: scale?.clamp(minimumOverlayScale, maximumOverlayScale),
      rotation: rotation == null ? null : _normalize(rotation),
    );
    final overlays = [..._value.overlays]..[index] = updated;
    _value = _value.copyWith(overlays: overlays);
    _changed();
    return true;
  }

  bool removeOverlay(String instanceId) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    if (!_value.overlays.any((item) => item.instanceId == instanceId)) {
      return false;
    }
    _value = _value.copyWith(
      overlays:
          _value.overlays
              .where((item) => item.instanceId != instanceId)
              .toList(),
    );
    if (_selectedOverlayId == instanceId) _selectedOverlayId = null;
    _changed();
    return true;
  }

  bool updateSticker(
    String instanceId, {
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    final index = _value.stickers.indexWhere(
      (item) => item.instanceId == instanceId,
    );
    if (index < 0) return false;
    final current = _value.stickers[index];
    final config = theme.sticker(current.stickerId);
    final workspace = _workspace;
    if ((centerX != null || centerY != null) &&
        (!config.canMove ||
            (workspace != null && !_allowed(workspace, 'move')))) {
      return false;
    }
    if (scale != null &&
        (!config.canResize ||
            (workspace != null && !_allowed(workspace, 'resize')))) {
      return false;
    }
    if (rotation != null &&
        (!config.canRotate ||
            (workspace != null && !_allowed(workspace, 'rotate')))) {
      return false;
    }
    final updated = current.copyWith(
      centerX: centerX?.clamp(0.02, 0.98),
      centerY: centerY?.clamp(0.02, 0.98),
      scale: scale?.clamp(config.minimumScale, config.maximumScale),
      rotation: rotation == null ? null : _normalize(rotation),
    );
    final stickers = [..._value.stickers]..[index] = updated;
    _value = _value.copyWith(stickers: stickers);
    _changed();
    return true;
  }

  bool removeSticker(String instanceId) {
    if (mode == ShareEditorMode.runtime &&
        !activeTemplate.runtimePermissions.userCanEditDecorations) {
      return false;
    }
    final current = _value.stickers.where(
      (item) => item.instanceId == instanceId,
    );
    if (current.isEmpty) return false;
    final config = theme.sticker(current.first.stickerId);
    final workspace = _workspace;
    if (!config.canDelete ||
        (workspace != null && !_allowed(workspace, 'delete'))) {
      return false;
    }
    _value = _value.copyWith(
      stickers:
          _value.stickers
              .where((item) => item.instanceId != instanceId)
              .toList(),
    );
    if (_selectedStickerId == instanceId) _selectedStickerId = null;
    _changed();
    return true;
  }

  /// Safety escape hatch used after a photo changes. It intentionally bypasses
  /// runtime decoration permissions because removing uncertain stickers must
  /// never depend on whether the public editor exposes decoration controls.
  void suppressSemanticStickers() {
    if (_value.stickers.isEmpty) return;
    _value = _value.copyWith(stickers: const []);
    _selectedStickerId = null;
    _changed();
  }

  void reset() {
    _value = _initial;
    _selectedLayerId = null;
    _selectedStickerId = null;
    _selectedOverlayId = null;
    _nextSticker = 1;
    _nextOverlay = 1;
    _hasChanges = false;
    notifyListeners();
  }

  ShareLayerConfig? get _workspace {
    for (final layer in theme.layers) {
      if (layer.type == 'stickerWorkspace') return layer;
    }
    return null;
  }

  bool _allowed(ShareLayerConfig layer, String controlId) {
    if (!canAccess(layer.access)) return false;
    ShareControlConfig? control = layer.control(controlId);
    if (control == null) {
      for (final candidate in layer.controls) {
        if (candidate.capability == controlId) {
          control = candidate;
          break;
        }
      }
    }
    return control != null &&
        canAccess(control.access) &&
        _runtimeAllows(layer, control.capability);
  }

  bool _runtimeAllows(ShareLayerConfig layer, String capability) {
    if (mode == ShareEditorMode.authoring) return true;
    final layerPermissions = layer.runtimePermissions;
    return switch (capability) {
      'edit' =>
        layerPermissions.canEditContent &&
            switch (layer.semanticRole) {
              ShareSemanticRole.headline =>
                activeTemplate.runtimePermissions.userCanEditHeadline,
              ShareSemanticRole.proof ||
              ShareSemanticRole.metric ||
              ShareSemanticRole.progress =>
                activeTemplate.runtimePermissions.userCanEditProofValue,
              _ => true,
            },
      'replace' =>
        layerPermissions.canReplaceMedia &&
            activeTemplate.runtimePermissions.userCanReplaceMedia,
      'crop' =>
        layerPermissions.canCropMedia &&
            activeTemplate.runtimePermissions.userCanCropMedia,
      'move' => layerPermissions.canMove,
      'resize' => layerPermissions.canResize,
      'rotate' => layerPermissions.canRotate,
      'hide' =>
        layerPermissions.canHide &&
            activeTemplate.runtimePermissions.userCanHideOptionalNote,
      _ => layerPermissions.canStyle,
    };
  }

  void _changed() {
    _hasChanges = true;
    notifyListeners();
  }

  double _normalize(double value) {
    var normalized = value % (math.pi * 2);
    if (normalized > math.pi) normalized -= math.pi * 2;
    if (normalized < -math.pi) normalized += math.pi * 2;
    return normalized;
  }

  static ShareEditorValue _validatedInitial(
    ShareThemeConfig theme,
    ShareEditorContent content,
    ShareEditorValue? candidate,
  ) {
    if (candidate != null) {
      theme.look(candidate.lookId);
      final templateId = candidate.templateId ?? theme.defaultTemplateId;
      theme.template(templateId);
      if (candidate.backgroundId != null) {
        theme.background(candidate.backgroundId!);
      }
      for (final layerId in candidate.layerValues.keys) {
        theme.layer(layerId);
      }
      for (final layerId in candidate.transforms.keys) {
        theme.layer(layerId);
        final transform = candidate.transforms[layerId]!;
        if (transform.width <= 0 ||
            transform.height <= 0 ||
            transform.x < 0 ||
            transform.y < 0 ||
            transform.x + transform.width > theme.canvas.width + 0.001 ||
            transform.y + transform.height > theme.canvas.height + 0.001) {
          throw FormatException(
            'Saved transform for $layerId is outside the canvas',
          );
        }
      }
      if (candidate.stickers.length > theme.maximumStickerCount) {
        throw const FormatException('Saved composition has too many stickers');
      }
      if (candidate.stickers.length + candidate.overlays.length >
          theme.maximumDecorationCount) {
        throw const FormatException(
          'Saved composition has too many decoration layers',
        );
      }
      final instanceIds = <String>{};
      for (final item in candidate.stickers) {
        final config = theme.sticker(item.stickerId);
        if (!instanceIds.add(item.instanceId)) {
          throw FormatException(
            'Saved composition has duplicate sticker ${item.instanceId}',
          );
        }
        if (item.centerX < 0 ||
            item.centerX > 1 ||
            item.centerY < 0 ||
            item.centerY > 1 ||
            item.scale < config.minimumScale ||
            item.scale > config.maximumScale) {
          throw FormatException(
            'Saved sticker ${item.instanceId} is outside its constraints',
          );
        }
      }
      for (final item in candidate.overlays) {
        if (!instanceIds.add(item.instanceId)) {
          throw FormatException(
            'Saved composition has duplicate overlay ${item.instanceId}',
          );
        }
        if (item.centerX < 0 ||
            item.centerX > 1 ||
            item.centerY < 0 ||
            item.centerY > 1 ||
            item.scale < minimumOverlayScale ||
            item.scale > maximumOverlayScale) {
          throw FormatException(
            'Saved overlay ${item.instanceId} is outside its constraints',
          );
        }
      }
      _validatedBackgroundEdit(
        candidate.backgroundEdit,
        rejectOutOfRange: true,
      );
      for (final entry in candidate.propertyOverrides.entries) {
        final layer = theme.layer(entry.key);
        for (final property in entry.value.entries) {
          final control = layer.control(property.key);
          if (control == null) {
            throw FormatException(
              'Saved property ${entry.key}.${property.key} is not exposed',
            );
          }
          final value = property.value;
          if (value is num &&
              ((control.minimum != null && value < control.minimum!) ||
                  (control.maximum != null && value > control.maximum!))) {
            throw FormatException(
              'Saved property ${entry.key}.${property.key} is outside its range',
            );
          }
          if (control.options.isNotEmpty &&
              !control.options.contains('$value')) {
            throw FormatException(
              'Saved property ${entry.key}.${property.key} is not allowed',
            );
          }
        }
      }
      return candidate.templateId == null
          ? candidate.copyWith(templateId: templateId)
          : candidate;
    }
    final look = theme.look(theme.defaultLookId);
    return ShareEditorValue(
      lookId: look.id,
      templateId: theme.defaultTemplateId,
      backgroundId: look.backgroundId ?? theme.defaultBackgroundId,
      layerValues: {
        for (final layer in theme.layers)
          if (layer.binding != null || layer.defaultValue != null)
            layer.id:
                (layer.binding == null
                    ? null
                    : content.resolve(layer.binding!)) ??
                layer.defaultValue,
      },
      transforms: const {},
      stickers: look.defaultStickers,
      backgroundEdit: look.backgroundTreatment,
    );
  }

  static ShareBackgroundEdit _validatedBackgroundEdit(
    ShareBackgroundEdit value, {
    bool rejectOutOfRange = false,
  }) {
    double number(
      String name,
      double candidate,
      double minimum,
      double maximum,
    ) {
      if (!candidate.isFinite ||
          (rejectOutOfRange && (candidate < minimum || candidate > maximum))) {
        throw FormatException(
          'Background treatment $name is outside its range',
        );
      }
      return candidate.clamp(minimum, maximum);
    }

    String color(String candidate) {
      if (!RegExp(
        r'^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$',
      ).hasMatch(candidate)) {
        throw const FormatException('Background treatment has invalid color');
      }
      return candidate.startsWith('#') ? candidate : '#$candidate';
    }

    return value.copyWith(
      alignmentX: number('alignmentX', value.alignmentX, -1, 1),
      alignmentY: number('alignmentY', value.alignmentY, -1, 1),
      zoom: number('zoom', value.zoom, 1, 4),
      imageOpacity: number('imageOpacity', value.imageOpacity, 0.2, 1),
      blur: number('blur', value.blur, 0, 30),
      brightness: number('brightness', value.brightness, -1, 1),
      contrast: number('contrast', value.contrast, 0.5, 2),
      saturation: number('saturation', value.saturation, 0, 2),
      tintColor: color(value.tintColor),
      tintOpacity: number('tintOpacity', value.tintOpacity, 0, 1),
      overlayColor: color(value.overlayColor),
      overlayOpacity: number('overlayOpacity', value.overlayOpacity, 0, 1),
      textureColor: color(value.textureColor),
      textureSecondaryColor: color(value.textureSecondaryColor),
      textureIntensity: number(
        'textureIntensity',
        value.textureIntensity,
        0,
        1,
      ),
      textureScale: number('textureScale', value.textureScale, 0.5, 4),
    );
  }

  static bool _denyEntitlements(String _) => false;
}
