import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../generated_share_editor/generated_share_editor.dart';

final class ThemeBuilderController extends ChangeNotifier {
  ThemeBuilderController(ShareThemeConfig initial)
    : _theme = initial,
      _savedJson = ShareThemeBundle.toJsonString(initial, pretty: false),
      selectedLookId = initial.defaultLookId,
      selectedLayerId = initial.layers.firstOrNull?.id;

  ShareThemeConfig _theme;
  String _savedJson;
  final List<String> _undo = [];
  final List<String> _redo = [];
  String? selectedLayerId;
  String selectedLookId;
  bool previewPremium = false;
  bool editLookOverrides = false;

  ShareThemeConfig get theme => _theme;
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

  ShareLayerConfig? get editingLayer {
    final layer = selectedLayer;
    if (layer == null || !editLookOverrides) return layer;
    final overrides = selectedLook.layerOverrides[layer.id];
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
    selectedLayerId = id;
    notifyListeners();
  }

  void selectLook(String id) {
    _theme.look(id);
    selectedLookId = id;
    notifyListeners();
  }

  void togglePremiumPreview(bool value) {
    previewPremium = value;
    notifyListeners();
  }

  void toggleLookOverrides(bool value) {
    editLookOverrides = value;
    notifyListeners();
  }

  void replaceFromJson(String raw, {bool markSaved = true}) {
    final next = ShareThemeBundle.fromJsonString(raw);
    _pushHistory();
    _theme = next;
    selectedLookId = next.defaultLookId;
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
    updateLayer(layer.copyWith(style: {...layer.style, property: value}));
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
    updateLayer(layer.copyWith(style: style));
  }

  void updateSelectedTransform(ShareLayerTransform transform) {
    final layer = selectedLayer;
    if (layer == null) return;
    final canvas = _theme.canvas;
    final width = transform.width.clamp(1.0, canvas.width);
    final height = transform.height.clamp(1.0, canvas.height);
    final constrained = transform.copyWith(
      x: transform.x.clamp(0.0, canvas.width - width),
      y: transform.y.clamp(0.0, canvas.height - height),
      width: width,
      height: height,
    );
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
    updateLayer(layer.copyWith(transform: constrained));
  }

  void updateSelectedVisibility(bool visible) {
    final layer = selectedLayer;
    if (layer == null) return;
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
    updateLayer(layer.copyWith(visible: visible));
  }

  void updateLayerAccess(ShareAccessPolicy access) {
    final layer = selectedLayer;
    if (layer == null) return;
    updateLayer(layer.copyWith(access: access));
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
          access: access ?? source.access,
        ).toJson();
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

  void removeLookSticker(String instanceId) {
    updateSelectedLook(
      defaultStickers:
          selectedLook.defaultStickers
              .where((item) => item.instanceId != instanceId)
              .toList(),
    );
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

  Future<void> addAsset({
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
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
