import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import 'studio_models.dart';

final class SocialPostStudioController extends ChangeNotifier {
  SocialPostStudioController({
    required this.catalog,
    SocialPostDraft? initialDraft,
  }) : _initialDraft = initialDraft ?? _defaultDraft(),
       _draft = initialDraft ?? _defaultDraft();

  static const maximumStickerCount = 3;
  static const maximumMessageLength = 100;
  static const maximumAvatarBytes = 10 * 1024 * 1024;

  static const _anchors = <(double, double)>[
    (0.78, 0.24),
    (0.22, 0.72),
    (0.78, 0.76),
  ];

  final MemeStickerCatalog catalog;
  final SocialPostDraft _initialDraft;
  SocialPostDraft _draft;
  MemeStickerCategory _category = MemeStickerCategory.hype;
  String? _selectedStickerId;
  int _nextInstanceNumber = 1;

  SocialPostDraft get draft => _draft;
  MemeStickerCategory get category => _category;
  String? get selectedStickerId => _selectedStickerId;
  bool get canAddSticker => _draft.stickers.length < maximumStickerCount;
  List<MemeStickerDefinition> get visibleStickers =>
      catalog.inCategory(_category);

  StickerPlacement? get selectedPlacement {
    for (final placement in _draft.stickers) {
      if (placement.instanceId == _selectedStickerId) return placement;
    }
    return null;
  }

  void updateMessage(String value) {
    final next =
        value.length <= maximumMessageLength
            ? value
            : value.substring(0, maximumMessageLength);
    if (next == _draft.message) return;
    _draft = _draft.copyWith(message: next);
    notifyListeners();
  }

  void setAvatarBytes(Uint8List bytes) {
    if (bytes.isEmpty) throw ArgumentError('Avatar bytes cannot be empty');
    if (bytes.length > maximumAvatarBytes) {
      throw ArgumentError('Avatar image exceeds 10 MB');
    }
    _draft = _draft.copyWith(avatar: StudioImageRef.memory(bytes));
    notifyListeners();
  }

  void selectBackground(String id) {
    StudioBackgrounds.byId(id);
    if (id == _draft.backgroundId) return;
    _draft = _draft.copyWith(backgroundId: id);
    notifyListeners();
  }

  void selectCategory(MemeStickerCategory value) {
    if (value == _category) return;
    _category = value;
    notifyListeners();
  }

  bool addSticker(String stickerId) {
    if (!canAddSticker) return false;
    final definition = catalog.byId(stickerId);
    final anchor = _anchors[_draft.stickers.length];
    final instanceId = '${definition.id}_${_nextInstanceNumber++}';
    final placement = StickerPlacement(
      instanceId: instanceId,
      stickerId: definition.id,
      centerX: anchor.$1,
      centerY: anchor.$2,
      scale: definition.defaultScale,
      rotation: 0,
    );
    _draft = _draft.copyWith(stickers: [..._draft.stickers, placement]);
    _selectedStickerId = instanceId;
    notifyListeners();
    return true;
  }

  void selectSticker(String? instanceId) {
    if (instanceId != null &&
        !_draft.stickers.any((item) => item.instanceId == instanceId)) {
      return;
    }
    if (instanceId == _selectedStickerId) return;
    _selectedStickerId = instanceId;
    notifyListeners();
  }

  void updatePlacement(
    String instanceId, {
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) {
    final index = _draft.stickers.indexWhere(
      (item) => item.instanceId == instanceId,
    );
    if (index < 0) return;
    final current = _draft.stickers[index];
    final updated = current.copyWith(
      centerX: centerX?.clamp(0.0, 1.0),
      centerY: centerY?.clamp(0.0, 1.0),
      scale: scale?.clamp(
        StickerPlacement.minimumScale,
        StickerPlacement.maximumScale,
      ),
      rotation: rotation == null ? null : _normalizeRotation(rotation),
    );
    final placements = [..._draft.stickers]..[index] = updated;
    _draft = _draft.copyWith(stickers: placements);
    notifyListeners();
  }

  void nudgeSelected({required double dx, required double dy}) {
    final placement = selectedPlacement;
    if (placement == null) return;
    updatePlacement(
      placement.instanceId,
      centerX: placement.centerX + dx,
      centerY: placement.centerY + dy,
    );
  }

  bool duplicateSelected() {
    final placement = selectedPlacement;
    if (placement == null || !canAddSticker) return false;
    final instanceId = '${placement.stickerId}_${_nextInstanceNumber++}';
    final copy = StickerPlacement(
      instanceId: instanceId,
      stickerId: placement.stickerId,
      centerX: (placement.centerX + 0.05).clamp(0.0, 1.0),
      centerY: (placement.centerY + 0.05).clamp(0.0, 1.0),
      scale: placement.scale,
      rotation: placement.rotation,
    );
    _draft = _draft.copyWith(stickers: [..._draft.stickers, copy]);
    _selectedStickerId = instanceId;
    notifyListeners();
    return true;
  }

  void moveSelectedForward() => _moveSelected(1);

  void moveSelectedBackward() => _moveSelected(-1);

  void _moveSelected(int delta) {
    final index = _draft.stickers.indexWhere(
      (item) => item.instanceId == _selectedStickerId,
    );
    final nextIndex = index + delta;
    if (index < 0 || nextIndex < 0 || nextIndex >= _draft.stickers.length) {
      return;
    }
    final placements = [..._draft.stickers];
    final item = placements.removeAt(index);
    placements.insert(nextIndex, item);
    _draft = _draft.copyWith(stickers: placements);
    notifyListeners();
  }

  void removeSelected() {
    if (_selectedStickerId == null) return;
    final placements = _draft.stickers
        .where((item) => item.instanceId != _selectedStickerId)
        .toList(growable: false);
    if (placements.length == _draft.stickers.length) return;
    _draft = _draft.copyWith(stickers: placements);
    _selectedStickerId = null;
    notifyListeners();
  }

  void reset() {
    _draft = _initialDraft;
    _category = MemeStickerCategory.hype;
    _selectedStickerId = null;
    _nextInstanceNumber = 1;
    notifyListeners();
  }

  static SocialPostDraft _defaultDraft() => SocialPostDraft(
    message: "tell me why\ni won't.",
    avatar: const StudioImageRef.asset('assets/images/users/alex.jpg'),
    backgroundId: 'startup',
    stickers: const [],
  );

  double _normalizeRotation(double value) {
    var normalized = value % (math.pi * 2);
    if (normalized > math.pi) normalized -= math.pi * 2;
    if (normalized < -math.pi) normalized += math.pi * 2;
    return normalized;
  }
}
