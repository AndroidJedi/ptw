import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import '../../models/ptw_story_composition.dart';
import 'story_look_presets.dart';
import 'studio_models.dart';

final class PtwStoryConstructorController extends ChangeNotifier {
  PtwStoryConstructorController({
    required this.catalog,
    required PtwStoryComposition initialComposition,
    required this.now,
  }) : _initial = initialComposition,
       _composition = initialComposition,
       _lookIndex = PtwStoryLooks.all.indexWhere(
         (item) => item.id == initialComposition.lookId,
       );

  static const maximumStickerCount = 3;

  final MemeStickerCatalog catalog;
  final DateTime Function() now;
  final PtwStoryComposition _initial;
  PtwStoryComposition _composition;
  int _lookIndex;
  int _nextSticker = 1;
  String? _selectedStickerId;
  bool _hasChanges = false;

  PtwStoryComposition get composition => _composition;
  bool get hasChanges => _hasChanges;
  bool get canAddSticker => _composition.stickers.length < maximumStickerCount;
  String? get selectedStickerId => _selectedStickerId;

  void cycleLook() {
    _lookIndex = (_lookIndex + 1) % PtwStoryLooks.all.length;
    _composition = PtwStoryLooks.apply(
      _composition,
      PtwStoryLooks.all[_lookIndex],
      now(),
    );
    _selectedStickerId = null;
    _changed();
  }

  void applyLook(PtwStoryLookPreset preset) {
    _lookIndex = PtwStoryLooks.all.indexOf(preset);
    _composition = PtwStoryLooks.apply(_composition, preset, now());
    _selectedStickerId = null;
    _changed();
  }

  void updateText({required String headline, required String dare}) {
    final safeHeadline = _trimTo(
      headline.trim(),
      PtwStoryComposition.maximumHeadlineLength,
    );
    final safeDare = _trimTo(
      dare.trim(),
      PtwStoryComposition.maximumDareLength,
    );
    _composition = _composition.copyWith(
      headline: safeHeadline,
      dare: safeDare,
      caption: '$safeHeadline\n$safeDare',
      updatedAt: now(),
    );
    _changed();
  }

  void selectBackground(String id) {
    StudioBackgrounds.byId(id);
    _composition = _composition.copyWith(
      backgroundId: id,
      lookId: 'custom',
      updatedAt: now(),
    );
    _changed();
  }

  void selectProjectBackground() {
    _composition = _composition.copyWith(
      clearBackgroundId: true,
      lookId: 'custom',
      updatedAt: now(),
    );
    _changed();
  }

  bool addSticker(String stickerId) {
    if (!canAddSticker) return false;
    final definition = catalog.byId(stickerId);
    final count = _composition.stickers.length;
    const anchors = [(0.78, 0.24), (0.22, 0.72), (0.78, 0.72)];
    final placement = PtwStoryStickerPlacement(
      instanceId: '${definition.id}_${_nextSticker++}',
      stickerId: stickerId,
      centerX: anchors[count].$1,
      centerY: anchors[count].$2,
      scale: definition.defaultScale.clamp(
        PtwStoryStickerPlacement.minimumScale,
        PtwStoryStickerPlacement.maximumScale,
      ),
      rotation: 0,
    );
    _composition = _composition.copyWith(
      stickers: [..._composition.stickers, placement],
      lookId: 'custom',
      updatedAt: now(),
    );
    _selectedStickerId = placement.instanceId;
    _changed();
    return true;
  }

  void selectSticker(String? instanceId) {
    _selectedStickerId = instanceId;
    notifyListeners();
  }

  void updateSticker(
    String instanceId, {
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) {
    final index = _composition.stickers.indexWhere(
      (item) => item.instanceId == instanceId,
    );
    if (index < 0) return;
    final current = _composition.stickers[index];
    final updated = current.copyWith(
      centerX: centerX?.clamp(0.05, 0.95),
      centerY: centerY?.clamp(0.05, 0.95),
      scale: scale?.clamp(
        PtwStoryStickerPlacement.minimumScale,
        PtwStoryStickerPlacement.maximumScale,
      ),
      rotation: rotation == null ? null : _normalize(rotation),
    );
    final stickers = [..._composition.stickers]..[index] = updated;
    _composition = _composition.copyWith(
      stickers: stickers,
      lookId: 'custom',
      updatedAt: now(),
    );
    _changed();
  }

  void removeSelected() {
    final id = _selectedStickerId;
    if (id == null) return;
    _composition = _composition.copyWith(
      stickers:
          _composition.stickers.where((item) => item.instanceId != id).toList(),
      lookId: 'custom',
      updatedAt: now(),
    );
    _selectedStickerId = null;
    _changed();
  }

  void reset() {
    _composition = _initial;
    _lookIndex = PtwStoryLooks.all.indexWhere(
      (item) => item.id == _initial.lookId,
    );
    _selectedStickerId = null;
    _hasChanges = false;
    notifyListeners();
  }

  void _changed() {
    _hasChanges = true;
    notifyListeners();
  }

  String _trimTo(String value, int length) =>
      value.length <= length ? value : value.substring(0, length);

  double _normalize(double value) {
    var normalized = value % (math.pi * 2);
    if (normalized > math.pi) normalized -= math.pi * 2;
    if (normalized < -math.pi) normalized += math.pi * 2;
    return normalized;
  }
}
