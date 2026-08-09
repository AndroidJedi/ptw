import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';

import '../../generated_share_editor/generated_share_editor.dart';

enum ThemeBuilderMode { explore, production }

enum _LayerGestureKind { move, resize, rotate }

final class ThemeBuilderController extends ChangeNotifier {
  ThemeBuilderController(ShareThemeConfig initial)
    : _theme = initial,
      _savedJson = ShareThemeBundle.toJsonString(initial, pretty: false),
      selectedLookId = initial.defaultLookId,
      selectedTemplateId = initial.defaultTemplateId,
      selectedLayerId = initial.layers.firstOrNull?.id;

  ShareThemeConfig _theme;
  String _savedJson;
  final List<String> _undo = [];
  final List<String> _redo = [];
  final ValueNotifier<ShareLayerConfig?> _liveLayerDraft = ValueNotifier(null);
  final ValueNotifier<ShareStickerValue?> _liveStickerDraft = ValueNotifier(
    null,
  );
  final ValueNotifier<ShareBackgroundEdit?> _liveBackgroundTreatmentDraft =
      ValueNotifier(null);
  final ValueNotifier<ShareBackgroundConfig?> _liveBackgroundDraft =
      ValueNotifier(null);
  ShareLayerConfig? _pendingLayerDraft;
  ShareStickerValue? _pendingStickerDraft;
  ShareBackgroundEdit? _pendingBackgroundTreatmentDraft;
  ShareBackgroundConfig? _pendingBackgroundDraft;
  bool _layerDraftFrameScheduled = false;
  bool _stickerDraftFrameScheduled = false;
  bool _backgroundTreatmentFrameScheduled = false;
  bool _backgroundDraftFrameScheduled = false;
  bool _disposed = false;
  ShareLayerTransform? _layerGestureStart;
  _LayerGestureKind? _layerGestureKind;
  double _layerGestureDeltaX = 0;
  double _layerGestureDeltaY = 0;
  double? _rotationPointerStart;
  double? _rotationBase;
  double? _rotationSnapTarget;
  String? _stickerGestureId;
  ShareStickerValue? _stickerGestureStart;
  String? _styleDraftProperty;
  Object? _styleDraftValue;
  String? selectedLayerId;
  String? selectedLookStickerId;
  String selectedLookId;
  String selectedTemplateId;
  ThemeBuilderMode mode = ThemeBuilderMode.explore;
  bool previewPremium = false;
  bool editLookOverrides = false;
  bool showGrid = true;
  bool showSafeZones = true;
  bool previewOnly = false;
  bool snapToGrid = true;
  double gridSize = 10;

  ShareThemeConfig get theme => _theme;
  ValueListenable<ShareLayerConfig?> get liveLayerDraft => _liveLayerDraft;
  ValueListenable<ShareStickerValue?> get liveStickerDraft => _liveStickerDraft;
  ValueListenable<ShareBackgroundEdit?> get liveBackgroundTreatmentDraft =>
      _liveBackgroundTreatmentDraft;
  ValueListenable<ShareBackgroundConfig?> get liveBackgroundDraft =>
      _liveBackgroundDraft;
  bool get canUndo => _undo.isNotEmpty;
  bool get canRedo => _redo.isNotEmpty;
  bool get hasUnsavedChanges =>
      ShareThemeBundle.toJsonString(_theme, pretty: false) != _savedJson;

  ShareLayerConfig? get selectedLayer {
    final id = selectedLayerId;
    if (id == null) return null;
    for (final item in _theme.layers) {
      if (item.id == id) return item;
    }
    return null;
  }

  ShareLookConfig get selectedLook => _theme.look(selectedLookId);
  ShareTemplateConfig get selectedTemplate =>
      _theme.template(selectedTemplateId);

  ShareStickerValue? get editingLookSticker {
    final draft = _pendingStickerDraft;
    if (draft != null && draft.instanceId == selectedLookStickerId) {
      return draft;
    }
    final id = selectedLookStickerId;
    if (id == null) return null;
    return selectedLook.defaultStickers.firstWhere(
      (item) => item.instanceId == id,
    );
  }

  ShareLayerConfig? get editingLayer {
    final draft = _pendingLayerDraft;
    if (draft != null && draft.id == selectedLayerId) return draft;
    final layer = selectedLayer;
    if (layer == null) return null;
    final structured = _applyLayerOverride(
      layer,
      selectedTemplate.layerOverrides[layer.id],
    );
    return _applyLayerOverride(
      structured,
      selectedLook.layerOverrides[layer.id],
    );
  }

  ShareLayerConfig _applyLayerOverride(
    ShareLayerConfig layer,
    Map<String, Object?>? overrides,
  ) {
    if (overrides == null) return layer;
    final rawTransform = overrides['transform'];
    final rawStyle = overrides['style'];
    return layer.copyWith(
      visible: overrides['visible'] as bool?,
      transform:
          rawTransform is Map<String, dynamic>
              ? ShareLayerTransform.fromJson(rawTransform)
              : layer.transform,
      style: {
        ...layer.style,
        if (rawStyle is Map<String, dynamic>) ...rawStyle,
      },
    );
  }

  void selectLayer(String? id) {
    if (id != null) _theme.layer(id);
    if (selectedLayerId == id && selectedLookStickerId == null) return;
    cancelSelectedLayerTransform();
    cancelLookStickerTransform();
    selectedLayerId = id;
    selectedLookStickerId = null;
    notifyListeners();
  }

  void selectLookSticker(String? instanceId) {
    if (instanceId != null &&
        !selectedLook.defaultStickers.any(
          (item) => item.instanceId == instanceId,
        )) {
      throw ArgumentError.value(instanceId, 'instanceId');
    }
    if (selectedLookStickerId == instanceId &&
        (instanceId == null || selectedLayerId == null)) {
      return;
    }
    cancelSelectedLayerTransform();
    cancelLookStickerTransform();
    selectedLookStickerId = instanceId;
    if (instanceId != null) selectedLayerId = null;
    notifyListeners();
  }

  void selectLook(String id) {
    _theme.look(id);
    selectedLookId = id;
    selectedLookStickerId = null;
    notifyListeners();
  }

  void selectTemplate(String id) {
    _theme.template(id);
    selectedTemplateId = id;
    selectedLookStickerId = null;
    notifyListeners();
  }

  void setMode(ThemeBuilderMode value) {
    mode = value;
    if (mode == ThemeBuilderMode.production) editLookOverrides = false;
    notifyListeners();
  }

  void updateGrid({bool? visible, bool? snap, double? size}) {
    showGrid = visible ?? showGrid;
    snapToGrid = snap ?? snapToGrid;
    if (size != null && size.isFinite) gridSize = size.clamp(2, 100);
    notifyListeners();
  }

  void toggleSafeZones(bool value) {
    showSafeZones = value;
    notifyListeners();
  }

  void togglePreviewOnly(bool value) {
    previewOnly = value;
    notifyListeners();
  }

  void togglePremiumPreview(bool value) {
    previewPremium = value;
    notifyListeners();
  }

  void toggleLookOverrides(bool value) {
    if (mode == ThemeBuilderMode.production) return;
    editLookOverrides = value;
    notifyListeners();
  }

  void replaceFromJson(String raw, {bool markSaved = true}) {
    final next = ShareThemeBundle.fromJsonString(raw);
    _pushHistory();
    _theme = next;
    selectedLookId = next.defaultLookId;
    selectedTemplateId = next.defaultTemplateId;
    selectedLayerId = next.layers.firstOrNull?.id;
    if (markSaved) {
      _savedJson = ShareThemeBundle.toJsonString(next, pretty: false);
    }
    notifyListeners();
  }

  void markSaved() {
    _savedJson = ShareThemeBundle.toJsonString(_theme, pretty: false);
    notifyListeners();
  }

  void updateMetadata({
    String? id,
    String? name,
    double? width,
    double? height,
    int? outputWidth,
    int? outputHeight,
    double? safeInset,
    double? cornerRadius,
    int? maximumStickerCount,
    String? premiumIcon,
  }) {
    final json = _copyJson();
    if (id != null) json['id'] = id;
    if (name != null) json['name'] = name;
    final canvas = Map<String, dynamic>.from(json['canvas'] as Map);
    if (width != null) canvas['width'] = width;
    if (height != null) canvas['height'] = height;
    if (outputWidth != null) canvas['outputWidth'] = outputWidth;
    if (outputHeight != null) canvas['outputHeight'] = outputHeight;
    if (safeInset != null) canvas['safeInset'] = safeInset;
    if (cornerRadius != null) canvas['cornerRadius'] = cornerRadius;
    json['canvas'] = canvas;
    if (maximumStickerCount != null) {
      json['maximumStickerCount'] = maximumStickerCount;
    }
    if (premiumIcon != null) json['premiumIcon'] = premiumIcon;
    _commit(json);
  }

  void updateLayer(ShareLayerConfig layer) {
    final json = _copyJson();
    final layers =
        (json['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = layers.indexWhere((item) => item['id'] == layer.id);
    if (index < 0) throw ArgumentError.value(layer.id, 'layer.id');
    layers[index] = layer.toJson();
    _commit(json);
  }

  void updateLayerStyle(String property, Object? value) {
    final layer = selectedLayer;
    if (layer == null) return;
    if (editLookOverrides) {
      final overrides = <String, Map<String, Object?>>{
        ...selectedLook.layerOverrides,
      };
      final current = <String, Object?>{...?overrides[layer.id]};
      final style = <String, Object?>{
        if (current['style'] is Map<String, Object?>)
          ...(current['style']! as Map<String, Object?>),
        property: value,
      };
      current['style'] = style;
      overrides[layer.id] = current;
      updateSelectedLook(layerOverrides: overrides);
      return;
    }
    _updateBaseLayerClearingActiveOverrides(
      layer.copyWith(style: {...layer.style, property: value}),
      clearStyleProperties: {property},
    );
  }

  void replaceLayerStyle(Map<String, Object?> style) {
    final layer = selectedLayer;
    if (layer == null) return;
    if (editLookOverrides) {
      final overrides = <String, Map<String, Object?>>{
        ...selectedLook.layerOverrides,
        layer.id: {...?selectedLook.layerOverrides[layer.id], 'style': style},
      };
      updateSelectedLook(layerOverrides: overrides);
      return;
    }
    _updateBaseLayerClearingActiveOverrides(
      layer.copyWith(style: style),
      clearFields: const {'style'},
    );
  }

  void updateSelectedTransform(
    ShareLayerTransform transform, {
    bool useGrid = false,
    bool useSmartAlignment = false,
  }) {
    final layer = selectedLayer;
    if (layer == null) return;
    final constrained = _constrainedTransform(
      transform,
      useGrid: useGrid,
      useSmartAlignment: useSmartAlignment,
    );
    if (mode == ThemeBuilderMode.production) {
      _updateTemplateLayerOverride(layer.id, {
        'transform': constrained.toJson(),
      });
      return;
    }
    if (editLookOverrides) {
      final overrides = <String, Map<String, Object?>>{
        ...selectedLook.layerOverrides,
      };
      overrides[layer.id] = {
        ...?overrides[layer.id],
        'transform': constrained.toJson(),
      };
      updateSelectedLook(layerOverrides: overrides);
      return;
    }
    _updateBaseLayerClearingActiveOverrides(
      layer.copyWith(transform: constrained),
      clearFields: const {'transform'},
    );
  }

  void snapSelectedTransform() {
    final layer = editingLayer;
    if (layer == null || !snapToGrid) return;
    updateSelectedTransform(
      layer.transform,
      useGrid: true,
      useSmartAlignment: true,
    );
  }

  void beginSelectedLayerTransform() {
    cancelSelectedLayerTransform();
    _layerGestureStart = editingLayer?.transform;
    _layerGestureDeltaX = 0;
    _layerGestureDeltaY = 0;
  }

  void moveSelectedLayerBy({required double deltaX, required double deltaY}) {
    final start = _layerGestureStart ?? editingLayer?.transform;
    if (start == null) return;
    _layerGestureStart ??= start;
    _layerGestureKind = _LayerGestureKind.move;
    _layerGestureDeltaX += deltaX;
    _layerGestureDeltaY += deltaY;
    _previewSelectedTransform(
      start.copyWith(
        x: start.x + _layerGestureDeltaX,
        y: start.y + _layerGestureDeltaY,
      ),
      useSmartAlignment: true,
    );
  }

  void resizeSelectedLayerBy({
    required double deltaWidth,
    required double deltaHeight,
  }) {
    final start = _layerGestureStart ?? editingLayer?.transform;
    if (start == null) return;
    _layerGestureStart ??= start;
    _layerGestureKind = _LayerGestureKind.resize;
    _layerGestureDeltaX += deltaWidth;
    _layerGestureDeltaY += deltaHeight;
    _previewSelectedTransform(
      start.copyWith(
        width: (start.width + _layerGestureDeltaX).clamp(8, double.infinity),
        height: (start.height + _layerGestureDeltaY).clamp(8, double.infinity),
      ),
    );
  }

  void rotateSelectedLayerBy(double delta) {
    final start = _layerGestureStart ?? editingLayer?.transform;
    if (start == null) return;
    _layerGestureStart ??= start;
    _layerGestureKind = _LayerGestureKind.rotate;
    _layerGestureDeltaX += delta;
    _previewSelectedTransform(
      start.copyWith(
        rotation: _magnetizedRotation(start.rotation + _layerGestureDeltaX),
      ),
    );
  }

  void beginSelectedLayerRotation(double pointerAngle) {
    beginSelectedLayerTransform();
    final start = _layerGestureStart;
    if (start == null) return;
    _layerGestureKind = _LayerGestureKind.rotate;
    _rotationPointerStart = pointerAngle;
    _rotationBase = start.rotation;
  }

  void rotateSelectedLayerTo(double pointerAngle) {
    final pointerStart = _rotationPointerStart;
    final rotationBase = _rotationBase;
    if (pointerStart == null || rotationBase == null) return;
    final delta = _normalizeAngle(pointerAngle - pointerStart);
    _previewSelectedTransform(
      _layerGestureStart!.copyWith(
        rotation: _magnetizedRotation(rotationBase + delta),
      ),
    );
  }

  void finishSelectedLayerTransform() {
    final draft = _pendingLayerDraft;
    if (draft == null) {
      _resetLayerGesture();
      return;
    }
    var transform = draft.transform;
    if (_layerGestureKind != _LayerGestureKind.rotate && snapToGrid) {
      transform = _constrainedTransform(
        transform,
        useGrid: true,
        useSmartAlignment: _layerGestureKind == _LayerGestureKind.move,
      );
    }
    _resetLayerGesture(keepDraft: true);
    updateSelectedTransform(transform);
    _clearLayerDraft();
  }

  void cancelSelectedLayerTransform() {
    _resetLayerGesture();
    _clearLayerDraft();
  }

  void beginSelectedLayerStyleEdit() {
    cancelSelectedLayerTransform();
    _styleDraftProperty = null;
    _styleDraftValue = null;
  }

  void previewSelectedLayerStyle(String property, Object? value) {
    final layer = _pendingLayerDraft ?? editingLayer;
    if (layer == null) return;
    _styleDraftProperty = property;
    _styleDraftValue = value;
    _queueLayerDraft(layer.copyWith(style: {...layer.style, property: value}));
  }

  void finishSelectedLayerStyleEdit() {
    final property = _styleDraftProperty;
    final value = _styleDraftValue;
    _styleDraftProperty = null;
    _styleDraftValue = null;
    if (property != null) updateLayerStyle(property, value);
    _clearLayerDraft();
  }

  void cancelSelectedLayerStyleEdit() {
    _styleDraftProperty = null;
    _styleDraftValue = null;
    _clearLayerDraft();
  }

  void beginBackgroundTreatmentEdit() {
    cancelBackgroundTreatmentEdit();
  }

  void previewBackgroundTreatment(ShareBackgroundEdit value) {
    _pendingBackgroundTreatmentDraft = value;
    if (_backgroundTreatmentFrameScheduled) return;
    _backgroundTreatmentFrameScheduled = true;
    SchedulerBinding.instance.scheduleFrameCallback((_) {
      if (!_backgroundTreatmentFrameScheduled || _disposed) return;
      _backgroundTreatmentFrameScheduled = false;
      final next = _pendingBackgroundTreatmentDraft;
      if (_liveBackgroundTreatmentDraft.value != next) {
        _liveBackgroundTreatmentDraft.value = next;
      }
    });
  }

  void finishBackgroundTreatmentEdit() {
    final draft = _pendingBackgroundTreatmentDraft;
    _backgroundTreatmentFrameScheduled = false;
    if (draft != null) updateSelectedLook(backgroundTreatment: draft);
    _clearBackgroundTreatmentDraft();
  }

  void cancelBackgroundTreatmentEdit() {
    _clearBackgroundTreatmentDraft();
  }

  void _clearBackgroundTreatmentDraft() {
    _pendingBackgroundTreatmentDraft = null;
    _backgroundTreatmentFrameScheduled = false;
    if (_liveBackgroundTreatmentDraft.value != null) {
      _liveBackgroundTreatmentDraft.value = null;
    }
  }

  void beginBackgroundEdit() {
    cancelBackgroundEdit();
  }

  void previewBackground(ShareBackgroundConfig value) {
    _pendingBackgroundDraft = value;
    if (_backgroundDraftFrameScheduled) return;
    _backgroundDraftFrameScheduled = true;
    SchedulerBinding.instance.scheduleFrameCallback((_) {
      if (!_backgroundDraftFrameScheduled || _disposed) return;
      _backgroundDraftFrameScheduled = false;
      final next = _pendingBackgroundDraft;
      if (_liveBackgroundDraft.value != next) {
        _liveBackgroundDraft.value = next;
      }
    });
  }

  void finishBackgroundEdit() {
    final draft = _pendingBackgroundDraft;
    _backgroundDraftFrameScheduled = false;
    if (draft != null) updateBackground(draft);
    _clearBackgroundDraft();
  }

  void cancelBackgroundEdit() {
    _clearBackgroundDraft();
  }

  void _clearBackgroundDraft() {
    _pendingBackgroundDraft = null;
    _backgroundDraftFrameScheduled = false;
    if (_liveBackgroundDraft.value != null) {
      _liveBackgroundDraft.value = null;
    }
  }

  ShareLayerTransform _constrainedTransform(
    ShareLayerTransform transform, {
    bool useGrid = false,
    bool useSmartAlignment = false,
  }) {
    if (useGrid && snapToGrid) {
      final step = gridSize;
      double snap(double value) => (value / step).round() * step;
      transform = transform.copyWith(
        x: snap(transform.x),
        y: snap(transform.y),
        width: snap(transform.width).clamp(step, double.infinity),
        height: snap(transform.height).clamp(step, double.infinity),
      );
    }
    if (useSmartAlignment && snapToGrid) {
      transform = _smartAlignedTransform(transform);
    }
    final canvas = _theme.canvas;
    final width = transform.width.clamp(1.0, canvas.width);
    final height = transform.height.clamp(1.0, canvas.height);
    return transform.copyWith(
      x: transform.x.clamp(0.0, canvas.width - width),
      y: transform.y.clamp(0.0, canvas.height - height),
      width: width,
      height: height,
      rotation: _normalizeAngle(transform.rotation),
    );
  }

  void _previewSelectedTransform(
    ShareLayerTransform transform, {
    bool useSmartAlignment = false,
  }) {
    final layer = _pendingLayerDraft ?? editingLayer;
    if (layer == null) return;
    _queueLayerDraft(
      layer.copyWith(
        transform: _constrainedTransform(
          transform,
          useSmartAlignment: useSmartAlignment,
        ),
      ),
    );
  }

  void _queueLayerDraft(ShareLayerConfig layer) {
    _pendingLayerDraft = layer;
    if (_layerDraftFrameScheduled) return;
    _layerDraftFrameScheduled = true;
    SchedulerBinding.instance.scheduleFrameCallback((_) {
      if (!_layerDraftFrameScheduled || _disposed) return;
      _layerDraftFrameScheduled = false;
      _publishLayerDraft();
    });
  }

  void _publishLayerDraft() {
    final next = _pendingLayerDraft;
    if (_liveLayerDraft.value != next) _liveLayerDraft.value = next;
  }

  void _clearLayerDraft() {
    _pendingLayerDraft = null;
    _layerDraftFrameScheduled = false;
    if (_liveLayerDraft.value != null) _liveLayerDraft.value = null;
  }

  void _resetLayerGesture({bool keepDraft = false}) {
    _layerGestureStart = null;
    _layerGestureKind = null;
    _layerGestureDeltaX = 0;
    _layerGestureDeltaY = 0;
    _rotationPointerStart = null;
    _rotationBase = null;
    _rotationSnapTarget = null;
    if (!keepDraft) _pendingLayerDraft = null;
  }

  double _magnetizedRotation(double rotation) {
    final normalized = _normalizeAngle(rotation);
    final activeTarget = _rotationSnapTarget;
    if (activeTarget != null) {
      if (_angleDistance(normalized, activeTarget) <= _degrees(6)) {
        return activeTarget;
      }
      _rotationSnapTarget = null;
    }
    const quarterTurns = [-math.pi, -math.pi / 2, 0.0, math.pi / 2, math.pi];
    for (final target in quarterTurns) {
      if (_angleDistance(normalized, target) <= _degrees(4)) {
        _rotationSnapTarget = target;
        return target;
      }
    }
    return normalized;
  }

  double _normalizeAngle(double value) {
    var normalized = value % (math.pi * 2);
    if (normalized > math.pi) normalized -= math.pi * 2;
    if (normalized < -math.pi) normalized += math.pi * 2;
    return normalized;
  }

  double _angleDistance(double first, double second) =>
      _normalizeAngle(first - second).abs();

  double _degrees(double value) => value * math.pi / 180;

  ShareLayerTransform _smartAlignedTransform(ShareLayerTransform transform) {
    final canvas = _theme.canvas;
    final xTargets = <double>{
      0,
      canvas.safeInset,
      canvas.width / 2,
      canvas.width - canvas.safeInset,
      canvas.width,
    };
    final yTargets = <double>{
      0,
      canvas.safeInset,
      canvas.height / 2,
      canvas.height - canvas.safeInset,
      canvas.height,
    };
    for (final zone in selectedTemplate.safeZones) {
      final rect = zone.rect;
      xTargets.addAll([rect.x, rect.x + rect.width / 2, rect.x + rect.width]);
      yTargets.addAll([rect.y, rect.y + rect.height / 2, rect.y + rect.height]);
    }

    final threshold = (gridSize * 0.65).clamp(5.0, 9.0);
    double alignedOrigin(double origin, double length, Set<double> targets) {
      var bestCorrection = double.infinity;
      for (final anchor in [0.0, length / 2, length]) {
        final position = origin + anchor;
        for (final target in targets) {
          final correction = target - position;
          if (correction.abs() < bestCorrection.abs()) {
            bestCorrection = correction;
          }
        }
      }
      return bestCorrection.abs() <= threshold
          ? origin + bestCorrection
          : origin;
    }

    return transform.copyWith(
      x: alignedOrigin(transform.x, transform.width, xTargets),
      y: alignedOrigin(transform.y, transform.height, yTargets),
    );
  }

  void updateSelectedVisibility(bool visible) {
    final layer = selectedLayer;
    if (layer == null) return;
    if (mode == ThemeBuilderMode.production) {
      _updateTemplateLayerOverride(layer.id, {'visible': visible});
      return;
    }
    if (editLookOverrides) {
      final overrides = <String, Map<String, Object?>>{
        ...selectedLook.layerOverrides,
        layer.id: {
          ...?selectedLook.layerOverrides[layer.id],
          'visible': visible,
        },
      };
      updateSelectedLook(layerOverrides: overrides);
      return;
    }
    _updateBaseLayerClearingActiveOverrides(
      layer.copyWith(visible: visible),
      clearFields: const {'visible'},
    );
  }

  void _updateBaseLayerClearingActiveOverrides(
    ShareLayerConfig layer, {
    Set<String> clearFields = const {},
    Set<String> clearStyleProperties = const {},
  }) {
    final json = _copyJson();
    final layers =
        (json['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
    final layerIndex = layers.indexWhere((item) => item['id'] == layer.id);
    if (layerIndex < 0) throw ArgumentError.value(layer.id, 'layer.id');
    layers[layerIndex] = layer.toJson();

    void clearInCollection(String collectionKey, String selectedId) {
      final collection =
          (json[collectionKey] as List<dynamic>).cast<Map<String, dynamic>>();
      final itemIndex = collection.indexWhere(
        (item) => item['id'] == selectedId,
      );
      if (itemIndex < 0) return;
      final item = Map<String, dynamic>.from(collection[itemIndex]);
      final overrides = Map<String, dynamic>.from(
        item['layerOverrides'] as Map? ?? const {},
      );
      final override = Map<String, dynamic>.from(
        overrides[layer.id] as Map? ?? const {},
      );
      for (final field in clearFields) {
        override.remove(field);
      }
      if (clearStyleProperties.isNotEmpty) {
        final style = Map<String, dynamic>.from(
          override['style'] as Map? ?? const {},
        );
        for (final property in clearStyleProperties) {
          style.remove(property);
        }
        if (style.isEmpty) {
          override.remove('style');
        } else {
          override['style'] = style;
        }
      }
      if (override.isEmpty) {
        overrides.remove(layer.id);
      } else {
        overrides[layer.id] = override;
      }
      item['layerOverrides'] = overrides;
      collection[itemIndex] = item;
    }

    clearInCollection('templates', selectedTemplateId);
    clearInCollection('looks', selectedLookId);
    _commit(json);
  }

  void updateLayerAccess(ShareAccessPolicy access) {
    final layer = selectedLayer;
    if (layer == null) return;
    updateLayer(layer.copyWith(access: access));
  }

  void updateLayerSemantics({
    ShareSemanticRole? role,
    ShareLayerEmphasis? emphasis,
  }) {
    final layer = selectedLayer;
    if (layer == null) return;
    updateLayer(layer.copyWith(semanticRole: role, emphasis: emphasis));
  }

  void updateLayerRuntimePermissions(ShareLayerRuntimePermissions permissions) {
    final layer = selectedLayer;
    if (layer == null) return;
    updateLayer(layer.copyWith(runtimePermissions: permissions));
  }

  void updateControl(
    String controlId, {
    ShareAccessPolicy? access,
    String? label,
    String? capability,
    Object? defaultValue,
    double? minimum,
    double? maximum,
    List<String>? options,
  }) {
    final layer = selectedLayer;
    if (layer == null) return;
    final controls = [
      for (final item in layer.controls)
        item.id == controlId
            ? _updatedControl(
              item,
              access: access,
              label: label,
              capability: capability,
              defaultValue: defaultValue,
              minimum: minimum,
              maximum: maximum,
              options: options,
            )
            : item,
    ];
    updateLayer(layer.copyWith(controls: controls));
  }

  void addLayer(String type) {
    final json = _copyJson();
    final layers =
        (json['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
    final id = _nextId(type, layers.map((item) => item['id'] as String));
    final canvas = _theme.canvas;
    final z =
        layers.fold<int>(
          0,
          (value, item) =>
              (item['zIndex'] as int) > value ? item['zIndex'] as int : value,
        ) +
        1;
    final binding = type == 'text' ? 'custom.$id' : null;
    layers.add(
      ShareLayerConfig(
        id: id,
        label: _labelFor(type),
        type: type,
        zIndex: z,
        transform: ShareLayerTransform(
          x: canvas.width * 0.2,
          y: canvas.height * 0.3,
          width: canvas.width * 0.6,
          height: type == 'text' ? 80 : canvas.width * 0.35,
        ),
        binding: binding,
        defaultValue: type == 'text' ? 'New label' : null,
        style: _defaultStyle(type),
        controls: _defaultControls(type),
      ).toJson(),
    );
    _commit(json);
    selectedLayerId = id;
    notifyListeners();
  }

  void removeSelectedLayer() {
    final id = selectedLayerId;
    if (id == null || _theme.layers.length <= 1) return;
    final json = _copyJson();
    final layers =
        (json['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
    layers.removeWhere((item) => item['id'] == id);
    final looks = (json['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
    for (final look in looks) {
      final overrides = Map<String, dynamic>.from(
        look['layerOverrides'] as Map? ?? const {},
      )..remove(id);
      look['layerOverrides'] = overrides;
    }
    final templates =
        (json['templates'] as List<dynamic>).cast<Map<String, dynamic>>();
    for (final template in templates) {
      final overrides = Map<String, dynamic>.from(
        template['layerOverrides'] as Map? ?? const {},
      )..remove(id);
      template['layerOverrides'] = overrides;
    }
    selectedLayerId = layers.firstOrNull?['id'] as String?;
    _commit(json);
  }

  void moveSelectedLayer(int delta) {
    final layer = selectedLayer;
    if (layer == null) return;
    final sorted = [..._theme.layers];
    final current = sorted.indexWhere((item) => item.id == layer.id);
    final target = (current + delta).clamp(0, sorted.length - 1);
    if (target == current) return;
    final moved = sorted.removeAt(current);
    sorted.insert(target, moved);
    final json = _copyJson();
    json['layers'] = [
      for (var index = 0; index < sorted.length; index++)
        sorted[index].copyWith(zIndex: index).toJson(),
    ];
    _commit(json);
  }

  void updateSelectedLook({
    String? label,
    String? backgroundId,
    Map<String, Map<String, Object?>>? layerOverrides,
    List<ShareStickerValue>? defaultStickers,
    ShareBackgroundEdit? backgroundTreatment,
    ShareAccessPolicy? access,
  }) {
    final json = _copyJson();
    final looks = (json['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = looks.indexWhere((item) => item['id'] == selectedLookId);
    final source = _theme.look(selectedLookId);
    looks[index] =
        ShareLookConfig(
          id: source.id,
          label: label ?? source.label,
          backgroundId: backgroundId ?? source.backgroundId,
          layerOverrides: layerOverrides ?? source.layerOverrides,
          defaultStickers: defaultStickers ?? source.defaultStickers,
          backgroundTreatment:
              backgroundTreatment ?? source.backgroundTreatment,
          editorVisible: source.editorVisible,
          access: access ?? source.access,
        ).toJson();
    _commit(json);
  }

  void updateSelectedTemplate({
    String? label,
    ShareTemplateFamily? family,
    String? variant,
    String? narrativeIntent,
    ShareJourneyState? primaryJourneyState,
    Set<ShareJourneyState>? supportedJourneyStates,
    Set<ShareSemanticRole>? requiredContentRoles,
    Set<ShareSemanticRole>? optionalContentRoles,
    ShareTemplateRuntimePermissions? runtimePermissions,
    ShareSemanticRole? primaryAnchor,
    int? supportedMediaCount,
    bool? supportsComparison,
    bool? supportsProof,
    ShareTemplateStatus? status,
  }) {
    final json = _copyJson();
    final templates =
        (json['templates'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = templates.indexWhere(
      (item) => item['id'] == selectedTemplateId,
    );
    if (index < 0) return;
    final item = Map<String, dynamic>.from(templates[index]);
    final previousRoles = <ShareSemanticRole>{
      ...selectedTemplate.requiredContentRoles,
      ...selectedTemplate.optionalContentRoles,
    };
    if (label != null) item['label'] = label;
    if (family != null) item['family'] = family.name;
    if (variant != null) item['variant'] = variant;
    if (narrativeIntent != null) item['narrativeIntent'] = narrativeIntent;
    if (primaryJourneyState != null) {
      item['primaryJourneyState'] = primaryJourneyState.name;
      final supported = List<String>.from(
        item['supportedJourneyStates'] as List? ?? const [],
      );
      if (!supported.contains(primaryJourneyState.name)) {
        supported.add(primaryJourneyState.name);
      }
      item['supportedJourneyStates'] = supported;
    }
    if (supportedJourneyStates != null) {
      item['supportedJourneyStates'] =
          supportedJourneyStates.map((value) => value.name).toList();
    }
    if (requiredContentRoles != null) {
      item['requiredContentRoles'] =
          requiredContentRoles.map((value) => value.name).toList();
    }
    if (optionalContentRoles != null) {
      item['optionalContentRoles'] =
          optionalContentRoles.map((value) => value.name).toList();
    }
    if (runtimePermissions != null) {
      item['runtimePermissions'] = runtimePermissions.toJson();
    }
    if (primaryAnchor != null) item['primaryAnchor'] = primaryAnchor.name;
    if (supportedMediaCount != null) {
      item['supportedMediaCount'] = supportedMediaCount;
    }
    if (supportsComparison != null) {
      item['supportsComparison'] = supportsComparison;
    }
    if (supportsProof != null) item['supportsProof'] = supportsProof;
    if (status != null) item['status'] = status.name;

    final layerOverrides = Map<String, dynamic>.from(
      item['layerOverrides'] as Map? ?? const {},
    );
    void setRolesVisible(Iterable<ShareSemanticRole> roles, bool visible) {
      final roleSet = roles.toSet();
      for (final layer in _theme.layers) {
        if (!roleSet.contains(layer.semanticRole)) continue;
        layerOverrides[layer.id] = {
          ...Map<String, dynamic>.from(
            layerOverrides[layer.id] as Map? ?? const {},
          ),
          'visible': visible,
        };
      }
    }

    if (requiredContentRoles != null || optionalContentRoles != null) {
      final nextRoles = <ShareSemanticRole>{
        ...(requiredContentRoles ?? selectedTemplate.requiredContentRoles),
        ...(optionalContentRoles ?? selectedTemplate.optionalContentRoles),
      };
      setRolesVisible(previousRoles.difference(nextRoles), false);
      setRolesVisible(nextRoles, true);
    }
    if (supportsComparison != null) {
      setRolesVisible(const {
        ShareSemanticRole.previousMedia,
        ShareSemanticRole.currentMedia,
        ShareSemanticRole.time,
      }, supportsComparison);
      if (supportsComparison &&
          (item['supportedMediaCount'] as num? ?? 0).toInt() < 2) {
        item['supportedMediaCount'] = 2;
      }
    }
    if (supportsProof != null) {
      setRolesVisible(const {
        ShareSemanticRole.proof,
        ShareSemanticRole.metric,
        ShareSemanticRole.progress,
      }, supportsProof);
    }
    item['layerOverrides'] = layerOverrides;
    templates[index] = item;
    _commit(json);
  }

  void _updateTemplateLayerOverride(
    String layerId,
    Map<String, Object?> patch,
  ) {
    final json = _copyJson();
    final templates =
        (json['templates'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = templates.indexWhere(
      (item) => item['id'] == selectedTemplateId,
    );
    final item = Map<String, dynamic>.from(templates[index]);
    final overrides = Map<String, dynamic>.from(
      item['layerOverrides'] as Map? ?? const {},
    );
    overrides[layerId] = {
      ...Map<String, dynamic>.from(overrides[layerId] as Map? ?? const {}),
      ...patch,
    };
    item['layerOverrides'] = overrides;
    templates[index] = item;
    _commit(json);
  }

  void addLookSticker(String stickerId) {
    if (selectedLook.defaultStickers.length >= _theme.maximumStickerCount) {
      return;
    }
    final config = _theme.sticker(stickerId);
    final existing = selectedLook.defaultStickers;
    var suffix = 1;
    final ids = existing.map((item) => item.instanceId).toSet();
    while (ids.contains('${stickerId}_$suffix')) {
      suffix++;
    }
    const anchors = [(0.76, 0.24), (0.24, 0.72), (0.76, 0.72)];
    final anchor = anchors[existing.length % anchors.length];
    updateSelectedLook(
      defaultStickers: [
        ...existing,
        ShareStickerValue(
          instanceId: '${stickerId}_$suffix',
          stickerId: stickerId,
          centerX: anchor.$1,
          centerY: anchor.$2,
          scale: config.defaultScale,
          rotation: 0,
        ),
      ],
    );
    selectedLookStickerId = '${stickerId}_$suffix';
    selectedLayerId = null;
    notifyListeners();
  }

  void updateLookSticker(
    String instanceId, {
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) {
    final values = [...selectedLook.defaultStickers];
    final index = values.indexWhere((item) => item.instanceId == instanceId);
    if (index < 0) return;
    final current = values[index];
    final config = _theme.sticker(current.stickerId);
    values[index] = current.copyWith(
      centerX: centerX?.clamp(0, 1),
      centerY: centerY?.clamp(0, 1),
      scale: scale?.clamp(config.minimumScale, config.maximumScale),
      rotation: rotation,
    );
    updateSelectedLook(defaultStickers: values);
  }

  void moveLookStickerBy(
    String instanceId, {
    required double deltaX,
    required double deltaY,
    required ShareLayerTransform workspace,
  }) {
    final current =
        _stickerGestureId == instanceId
            ? _pendingStickerDraft ?? _stickerGestureStart!
            : selectedLook.defaultStickers.firstWhere(
              (item) => item.instanceId == instanceId,
            );
    final next = current.copyWith(
      centerX: (current.centerX + deltaX / workspace.width).clamp(0, 1),
      centerY: (current.centerY + deltaY / workspace.height).clamp(0, 1),
    );
    if (_stickerGestureId == instanceId) {
      _queueStickerDraft(next);
      return;
    }
    updateLookSticker(instanceId, centerX: next.centerX, centerY: next.centerY);
  }

  void transformLookStickerBy(
    String instanceId, {
    required double scaleDelta,
    required double rotationDelta,
  }) {
    final current =
        _stickerGestureId == instanceId
            ? _pendingStickerDraft ?? _stickerGestureStart!
            : selectedLook.defaultStickers.firstWhere(
              (item) => item.instanceId == instanceId,
            );
    final config = _theme.sticker(current.stickerId);
    final next = current.copyWith(
      scale: (current.scale + scaleDelta).clamp(
        config.minimumScale,
        config.maximumScale,
      ),
      rotation: _normalizeAngle(current.rotation + rotationDelta),
    );
    if (_stickerGestureId == instanceId) {
      _queueStickerDraft(next);
      return;
    }
    updateLookSticker(instanceId, scale: next.scale, rotation: next.rotation);
  }

  void beginLookStickerTransform(String instanceId) {
    cancelLookStickerTransform();
    _stickerGestureId = instanceId;
    _stickerGestureStart = selectedLook.defaultStickers.firstWhere(
      (item) => item.instanceId == instanceId,
    );
  }

  void finishLookStickerTransform({ShareLayerTransform? workspace}) {
    final draft = _pendingStickerDraft;
    final id = _stickerGestureId;
    if (draft == null || id == null) {
      _resetStickerGesture();
      return;
    }
    final finalValue =
        snapToGrid && workspace != null
            ? _snappedSticker(draft, workspace)
            : draft;
    _resetStickerGesture(keepDraft: true);
    updateLookSticker(
      id,
      centerX: finalValue.centerX,
      centerY: finalValue.centerY,
      scale: finalValue.scale,
      rotation: finalValue.rotation,
    );
    _clearStickerDraft();
  }

  void cancelLookStickerTransform() {
    _resetStickerGesture();
    _clearStickerDraft();
  }

  void snapLookSticker(String instanceId) {
    if (!snapToGrid) return;
    final values = selectedLook.defaultStickers;
    final sticker = values.firstWhere((item) => item.instanceId == instanceId);
    final baseWorkspace = _theme.layers.firstWhere(
      (item) => item.type == 'stickerWorkspace',
    );
    final override = selectedLook.layerOverrides[baseWorkspace.id];
    final rawTransform = override?['transform'];
    final workspace =
        rawTransform is Map<String, dynamic>
            ? ShareLayerTransform.fromJson(rawTransform)
            : baseWorkspace.transform;
    final snapped = _snappedSticker(sticker, workspace);
    updateLookSticker(
      instanceId,
      centerX: snapped.centerX,
      centerY: snapped.centerY,
      scale: snapped.scale,
    );
  }

  ShareStickerValue _snappedSticker(
    ShareStickerValue sticker,
    ShareLayerTransform workspace,
  ) {
    double snap(double value) => (value / gridSize).round() * gridSize;
    final config = _theme.sticker(sticker.stickerId);
    return sticker.copyWith(
      centerX: (snap(sticker.centerX * workspace.width) / workspace.width)
          .clamp(0, 1),
      centerY: (snap(sticker.centerY * workspace.height) / workspace.height)
          .clamp(0, 1),
      scale: (snap(sticker.scale * workspace.width) / workspace.width).clamp(
        config.minimumScale,
        config.maximumScale,
      ),
    );
  }

  void _queueStickerDraft(ShareStickerValue sticker) {
    _pendingStickerDraft = sticker;
    if (_stickerDraftFrameScheduled) return;
    _stickerDraftFrameScheduled = true;
    SchedulerBinding.instance.scheduleFrameCallback((_) {
      if (!_stickerDraftFrameScheduled || _disposed) return;
      _stickerDraftFrameScheduled = false;
      final next = _pendingStickerDraft;
      if (_liveStickerDraft.value != next) _liveStickerDraft.value = next;
    });
  }

  void _clearStickerDraft() {
    _pendingStickerDraft = null;
    _stickerDraftFrameScheduled = false;
    if (_liveStickerDraft.value != null) _liveStickerDraft.value = null;
  }

  void _resetStickerGesture({bool keepDraft = false}) {
    _stickerGestureId = null;
    _stickerGestureStart = null;
    if (!keepDraft) _pendingStickerDraft = null;
  }

  void removeLookSticker(String instanceId) {
    updateSelectedLook(
      defaultStickers:
          selectedLook.defaultStickers
              .where((item) => item.instanceId != instanceId)
              .toList(),
    );
    if (selectedLookStickerId == instanceId) {
      selectedLookStickerId = null;
      notifyListeners();
    }
  }

  void updateStickerConfig(ShareStickerConfig sticker) {
    final minimum = sticker.minimumScale.clamp(0.01, 1.0);
    final maximum =
        sticker.maximumScale < minimum ? minimum : sticker.maximumScale;
    final normalized = sticker.copyWith(
      minimumScale: minimum,
      maximumScale: maximum,
      defaultScale: sticker.defaultScale.clamp(minimum, maximum),
    );
    final json = _copyJson();
    final stickers =
        (json['stickers'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = stickers.indexWhere((item) => item['id'] == normalized.id);
    if (index < 0) throw ArgumentError.value(normalized.id, 'sticker.id');
    stickers[index] = normalized.toJson();
    _commit(json);
  }

  void addStickerConfig(String assetId) {
    final asset = _theme.asset(assetId);
    if (asset.kind != 'image') return;
    final json = _copyJson();
    final stickers =
        (json['stickers'] as List<dynamic>).cast<Map<String, dynamic>>();
    final id = _nextId(asset.id, stickers.map((item) => item['id'] as String));
    stickers.add(
      ShareStickerConfig(
        id: id,
        label: asset.id,
        category: 'Custom',
        assetId: asset.id,
        defaultScale: 0.24,
      ).toJson(),
    );
    _commit(json);
  }

  void removeStickerConfig(String id) {
    final json = _copyJson();
    final stickers =
        (json['stickers'] as List<dynamic>).cast<Map<String, dynamic>>()
          ..removeWhere((item) => item['id'] == id);
    if (stickers.length == _theme.stickers.length) return;
    final looks = (json['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
    for (final look in looks) {
      final values =
          (look['defaultStickers'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .where((item) => item['stickerId'] != id)
              .toList();
      look['defaultStickers'] = values;
    }
    _commit(json);
  }

  void addLook() {
    final json = _copyJson();
    final looks = (json['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
    final source = selectedLook;
    final id = _nextId('look', looks.map((item) => item['id'] as String));
    looks.add(
      ShareLookConfig(
        id: id,
        label: 'New look',
        backgroundId: source.backgroundId,
        layerOverrides: source.layerOverrides,
        defaultStickers: source.defaultStickers,
        backgroundTreatment: source.backgroundTreatment,
        editorVisible: source.editorVisible,
        access: source.access,
      ).toJson(),
    );
    _commit(json);
    selectedLookId = id;
    notifyListeners();
  }

  void removeSelectedLook() {
    if (_theme.looks.length <= 1) return;
    final removedId = selectedLookId;
    final json = _copyJson();
    final looks = (json['looks'] as List<dynamic>).cast<Map<String, dynamic>>();
    looks.removeWhere((item) => item['id'] == selectedLookId);
    selectedLookId = looks.first['id'] as String;
    if (json['defaultLookId'] == removedId) {
      json['defaultLookId'] = selectedLookId;
    }
    _commit(json);
  }

  void addBackground(String kind) {
    final json = _copyJson();
    final backgrounds =
        (json['backgrounds'] as List<dynamic>).cast<Map<String, dynamic>>();
    final id = _nextId(kind, backgrounds.map((item) => item['id'] as String));
    final properties = switch (kind) {
      'solid' => <String, Object?>{'color': '#FF315CFF'},
      'image' => <String, Object?>{'binding': 'cover', 'fit': 'cover'},
      _ => <String, Object?>{
        'colors': ['#FFF4066E', '#FF315CFF'],
        'stops': [0, 1],
        'begin': 'topLeft',
        'end': 'bottomRight',
        'center': 'center',
        'radius': 0.8,
        'startAngle': 0,
        'endAngle': 6.283185307,
        'rotation': 0,
        'tileMode': 'clamp',
      },
    };
    backgrounds.add(
      ShareBackgroundConfig(
        id: id,
        label: 'New ${_labelFor(kind)}',
        kind: kind,
        properties: properties,
      ).toJson(),
    );
    _commit(json);
    updateSelectedLook(backgroundId: id);
  }

  void addPhotoBackground(String assetId, {String? label}) {
    final asset = _theme.asset(assetId);
    if (asset.kind != 'image') {
      throw ArgumentError.value(assetId, 'assetId', 'Expected an image asset');
    }
    final json = _copyJson();
    final backgrounds =
        (json['backgrounds'] as List<dynamic>).cast<Map<String, dynamic>>();
    final id = _nextId(
      'photo_${asset.id}',
      backgrounds.map((item) => item['id'] as String),
    );
    backgrounds.add(
      ShareBackgroundConfig(
        id: id,
        label: label?.trim().isNotEmpty == true ? label!.trim() : asset.id,
        kind: 'image',
        properties: {
          'assetId': asset.id,
          'fit': 'cover',
          'alignment': 'center',
          'overlayColor': '#00000000',
        },
      ).toJson(),
    );
    _commit(json);
  }

  void updateBackground(ShareBackgroundConfig background) {
    final json = _copyJson();
    final backgrounds =
        (json['backgrounds'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = backgrounds.indexWhere((item) => item['id'] == background.id);
    if (index < 0) throw ArgumentError.value(background.id, 'background.id');
    backgrounds[index] = background.toJson();
    _commit(json);
  }

  void updateToolbarAccess(String id, ShareAccessPolicy access) {
    updateToolbar(id, access: access);
  }

  void updateToolbar(
    String id, {
    String? label,
    String? icon,
    int? order,
    ShareAccessPolicy? access,
  }) {
    final json = _copyJson();
    final toolbar =
        (json['toolbar'] as List<dynamic>).cast<Map<String, dynamic>>();
    final index = toolbar.indexWhere((item) => item['id'] == id);
    final source = _theme.toolbar.firstWhere((item) => item.id == id);
    final updated =
        ShareToolbarGroupConfig(
          id: source.id,
          label: label ?? source.label,
          icon: icon ?? source.icon,
          order: order ?? source.order,
          access: access ?? source.access,
        ).toJson();
    if (order == null) {
      toolbar[index] = updated;
    } else {
      toolbar.removeAt(index);
      toolbar.insert(order.clamp(0, toolbar.length), updated);
      for (var position = 0; position < toolbar.length; position++) {
        toolbar[position]['order'] = position;
      }
    }
    _commit(json);
  }

  void setDefaultToolbarGroup(String id) {
    _theme.toolbar.firstWhere((item) => item.id == id);
    final json = _copyJson()..['defaultToolbarGroupId'] = id;
    _commit(json);
  }

  Future<String> addAsset({
    required String fileName,
    required String mimeType,
    required Uint8List bytes,
    required String kind,
    String? fontFamily,
  }) async {
    if (kind == 'font' && fontFamily != null) {
      final loader = FontLoader(fontFamily)
        ..addFont(Future.value(ByteData.sublistView(bytes)));
      await loader.load();
    }
    final json = _copyJson();
    final assets =
        (json['assets'] as List<dynamic>).cast<Map<String, dynamic>>();
    final base =
        fileName.replaceAll(RegExp(r'[^a-zA-Z0-9]+'), '_').toLowerCase();
    final id = _nextId(base, assets.map((item) => item['id'] as String));
    assets.add(
      ShareAssetConfig(
        id: id,
        kind: kind,
        mimeType: mimeType,
        data: base64Encode(bytes),
        fontFamily: fontFamily,
      ).toJson(),
    );
    _commit(json);
    return id;
  }

  void undo() {
    if (_undo.isEmpty) return;
    _redo.add(ShareThemeBundle.toJsonString(_theme, pretty: false));
    _theme = ShareThemeBundle.fromJsonString(_undo.removeLast());
    _repairSelection();
    notifyListeners();
  }

  void redo() {
    if (_redo.isEmpty) return;
    _undo.add(ShareThemeBundle.toJsonString(_theme, pretty: false));
    _theme = ShareThemeBundle.fromJsonString(_redo.removeLast());
    _repairSelection();
    notifyListeners();
  }

  Map<String, dynamic> _copyJson() =>
      jsonDecode(ShareThemeBundle.toJsonString(_theme, pretty: false))
          as Map<String, dynamic>;

  void _commit(Map<String, dynamic> json) {
    final next = ShareThemeConfig.fromJson(json);
    _pushHistory();
    _theme = next;
    notifyListeners();
  }

  void _pushHistory() {
    _undo.add(ShareThemeBundle.toJsonString(_theme, pretty: false));
    if (_undo.length > 100) _undo.removeAt(0);
    _redo.clear();
  }

  void _repairSelection() {
    if (!_theme.looks.any((item) => item.id == selectedLookId)) {
      selectedLookId = _theme.defaultLookId;
    }
    if (!_theme.layers.any((item) => item.id == selectedLayerId)) {
      selectedLayerId = _theme.layers.firstOrNull?.id;
    }
    if (!_theme.templates.any((item) => item.id == selectedTemplateId)) {
      selectedTemplateId = _theme.defaultTemplateId;
    }
    if (!selectedLook.defaultStickers.any(
      (item) => item.instanceId == selectedLookStickerId,
    )) {
      selectedLookStickerId = null;
    }
  }

  String _nextId(String prefix, Iterable<String> existing) {
    final safe = prefix
        .replaceAll(RegExp(r'[^a-zA-Z0-9_]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
    final ids = existing.toSet();
    if (!ids.contains(safe)) return safe;
    var suffix = 2;
    while (ids.contains('${safe}_$suffix')) {
      suffix++;
    }
    return '${safe}_$suffix';
  }

  static String _labelFor(String type) => switch (type) {
    'text' => 'Text',
    'image' => 'Photo',
    'asset' => 'Static asset',
    'shape' => 'Shape',
    'background' => 'Background',
    'stickerWorkspace' => 'Sticker workspace',
    'linear' => 'linear gradient',
    'radial' => 'radial gradient',
    'sweep' => 'sweep gradient',
    _ => type,
  };

  static Map<String, Object?> _defaultStyle(String type) => switch (type) {
    'text' => {
      'fontSize': 30,
      'fontWeight': 700,
      'color': '#FFFFFFFF',
      'maxLines': 3,
      'textAlign': 'center',
      'alignment': 'center',
      'autoSize': true,
      'minFontSize': 12,
    },
    'image' || 'asset' => {
      'fit': 'cover',
      'clip': 'rounded',
      'borderRadius': 16,
      'opacity': 1,
    },
    'shape' => {'shape': 'rectangle', 'color': '#66FFFFFF', 'borderRadius': 16},
    _ => {},
  };

  static List<ShareControlConfig> _defaultControls(String type) => [
    if (type == 'text' || type == 'image')
      const ShareControlConfig(
        id: 'edit',
        label: 'Edit',
        kind: ShareControlKind.action,
        capability: 'edit',
      ),
    const ShareControlConfig(
      id: 'move',
      label: 'Move',
      kind: ShareControlKind.action,
      capability: 'move',
    ),
    const ShareControlConfig(
      id: 'resize',
      label: 'Resize',
      kind: ShareControlKind.action,
      capability: 'resize',
    ),
    const ShareControlConfig(
      id: 'rotate',
      label: 'Rotate',
      kind: ShareControlKind.action,
      capability: 'rotate',
    ),
    if (type == 'text')
      const ShareControlConfig(
        id: 'fontSize',
        label: 'Text size',
        kind: ShareControlKind.number,
        capability: 'fontSize',
        defaultValue: 30,
        minimum: 8,
        maximum: 120,
      ),
  ];

  static ShareControlConfig _updatedControl(
    ShareControlConfig item, {
    ShareAccessPolicy? access,
    String? label,
    String? capability,
    Object? defaultValue,
    double? minimum,
    double? maximum,
    List<String>? options,
  }) {
    var nextMinimum = minimum ?? item.minimum;
    var nextMaximum = maximum ?? item.maximum;
    if (nextMinimum != null &&
        nextMaximum != null &&
        nextMinimum > nextMaximum) {
      if (minimum != null) {
        nextMaximum = nextMinimum;
      } else {
        nextMinimum = nextMaximum;
      }
    }
    final nextOptions = options ?? item.options;
    Object? nextDefault = defaultValue ?? item.defaultValue;
    if (nextDefault is num) {
      nextDefault = nextDefault.toDouble().clamp(
        nextMinimum ?? -double.maxFinite,
        nextMaximum ?? double.maxFinite,
      );
    }
    if (nextOptions.isNotEmpty && !nextOptions.contains('$nextDefault')) {
      nextDefault = nextOptions.first;
    }
    return ShareControlConfig(
      id: item.id,
      label: label ?? item.label,
      kind: item.kind,
      capability: capability ?? item.capability,
      defaultValue: nextDefault,
      minimum: nextMinimum,
      maximum: nextMaximum,
      options: nextOptions,
      access: access ?? item.access,
    );
  }

  @override
  void dispose() {
    _disposed = true;
    _liveLayerDraft.dispose();
    _liveStickerDraft.dispose();
    _liveBackgroundTreatmentDraft.dispose();
    _liveBackgroundDraft.dispose();
    super.dispose();
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
