import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import 'share_theme.dart';
import 'share_value.dart';

typedef ShareEntitlementResolver = bool Function(String entitlementKey);

enum ShareAccessState { available, locked, hidden }

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
  }) {
    final validated = _validatedInitial(theme, content, initialValue);
    return ShareEditorController._(
      theme: theme,
      content: content,
      initial: validated,
      entitlements: entitlements ?? _denyEntitlements,
    );
  }

  ShareEditorController._({
    required this.theme,
    required this.content,
    required ShareEditorValue initial,
    required ShareEntitlementResolver entitlements,
  }) : _entitlements = entitlements,
       _initial = initial,
       _value = initial {
    _nextSticker = 1;
  }

  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final ShareEntitlementResolver _entitlements;
  final ShareEditorValue _initial;
  ShareEditorValue _value;
  int _nextSticker = 1;
  String? _selectedLayerId;
  String? _selectedStickerId;
  bool _hasChanges = false;

  ShareEditorValue get value => _value;
  bool get hasChanges => _hasChanges;
  String? get selectedLayerId => _selectedLayerId;
  String? get selectedStickerId => _selectedStickerId;
  bool get canAddSticker => _value.stickers.length < theme.maximumStickerCount;

  ShareLookConfig get activeLook => theme.look(_value.lookId);

  ShareLayerConfig effectiveLayer(String layerId) {
    final base = theme.layer(layerId);
    final override = activeLook.layerOverrides[layerId];
    if (override == null) return base;
    final styleOverride = override['style'];
    final mergedStyle = <String, Object?>{
      ...base.style,
      if (styleOverride is Map<String, dynamic>) ...styleOverride,
      if (styleOverride is Map<String, Object?>) ...styleOverride,
    };
    final rawTransform = override['transform'];
    return base.copyWith(
      visible: override['visible'] as bool?,
      defaultValue: override['defaultValue'],
      transform:
          rawTransform is Map<String, dynamic>
              ? ShareLayerTransform.fromJson(rawTransform)
              : base.transform,
      style: mergedStyle,
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
    return control == null
        ? ShareAccessState.hidden
        : accessState(control.access);
  }

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
    notifyListeners();
  }

  void selectSticker(String? instanceId) {
    if (instanceId != null &&
        !_value.stickers.any((item) => item.instanceId == instanceId)) {
      return;
    }
    _selectedStickerId = instanceId;
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
    final layer = theme.layer(layerId);
    final control = layer.control(property);
    if (control == null || !canAccess(control.access)) return false;
    Object? safe = value;
    if (value is num) {
      safe = value.toDouble().clamp(
        control.minimum ?? -double.maxFinite,
        control.maximum ?? double.maxFinite,
      );
    }
    if (control.options.isNotEmpty && !control.options.contains('$safe')) {
      return false;
    }
    final overrides = <String, Map<String, Object?>>{
      ..._value.propertyOverrides,
      layerId: {...?_value.propertyOverrides[layerId], property: safe},
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
    final background = theme.background(backgroundId);
    if (!canAccess(background.access)) return false;
    _value = _value.copyWith(backgroundId: backgroundId);
    _changed();
    return true;
  }

  bool selectLook(String lookId) {
    final look = theme.look(lookId);
    if (!canAccess(look.access)) return false;
    _value = _value.copyWith(
      lookId: look.id,
      backgroundId: look.backgroundId ?? theme.defaultBackgroundId,
      stickers: look.defaultStickers,
      transforms: const {},
      propertyOverrides: const {},
    );
    _selectedLayerId = null;
    _selectedStickerId = null;
    _nextSticker = 1;
    _changed();
    return true;
  }

  bool cycleLook() {
    final visible =
        theme.looks
            .where(
              (item) => accessState(item.access) != ShareAccessState.hidden,
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

  bool addSticker(String stickerId) {
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

  void reset() {
    _value = _initial;
    _selectedLayerId = null;
    _selectedStickerId = null;
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
    return control != null && canAccess(control.access);
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
      return candidate;
    }
    final look = theme.look(theme.defaultLookId);
    return ShareEditorValue(
      lookId: look.id,
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
    );
  }

  static bool _denyEntitlements(String _) => false;
}
