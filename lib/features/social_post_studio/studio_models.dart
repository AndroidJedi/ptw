import 'dart:convert';

import 'package:flutter/services.dart';

enum MemeStickerCategory {
  hype,
  doubt,
  chaos;

  String get label => switch (this) {
    hype => 'Hype',
    doubt => 'Doubt',
    chaos => 'Chaos',
  };
}

final class MemeStickerDefinition {
  const MemeStickerDefinition({
    required this.id,
    required this.label,
    required this.category,
    required this.assetPath,
    required this.order,
    required this.defaultScale,
  });

  factory MemeStickerDefinition.fromJson(Map<String, dynamic> json) {
    final scale = _requiredDouble(json, 'defaultScale');
    if (scale < StickerPlacement.minimumScale ||
        scale > StickerPlacement.maximumScale) {
      throw FormatException('Sticker ${json['id']} has an invalid scale');
    }
    return MemeStickerDefinition(
      id: _requiredString(json, 'id'),
      label: _requiredString(json, 'label'),
      category: MemeStickerCategory.values.byName(
        _requiredString(json, 'category'),
      ),
      assetPath: _requiredString(json, 'assetPath'),
      order: _requiredInt(json, 'order'),
      defaultScale: scale,
    );
  }

  final String id;
  final String label;
  final MemeStickerCategory category;
  final String assetPath;
  final int order;
  final double defaultScale;
}

final class MemeStickerCatalog {
  MemeStickerCatalog({required List<MemeStickerDefinition> stickers})
    : stickers = List.unmodifiable(
        [...stickers]..sort((left, right) => left.order.compareTo(right.order)),
      ),
      _byId = Map.unmodifiable({
        for (final sticker in stickers) sticker.id: sticker,
      }) {
    if (stickers.isEmpty) {
      throw const FormatException('Sticker catalog cannot be empty');
    }
    if (_byId.length != stickers.length) {
      throw const FormatException('Sticker IDs must be unique');
    }
    final orders = stickers.map((item) => item.order).toSet();
    if (orders.length != stickers.length) {
      throw const FormatException('Sticker display order must be unique');
    }
  }

  factory MemeStickerCatalog.fromJson(Map<String, dynamic> json) {
    final raw = json['stickers'];
    if (raw is! List<dynamic>) {
      throw const FormatException('Sticker catalog requires a stickers list');
    }
    return MemeStickerCatalog(
      stickers: raw
          .map((item) {
            if (item is! Map<String, dynamic>) {
              throw const FormatException('Sticker must be an object');
            }
            return MemeStickerDefinition.fromJson(item);
          })
          .toList(growable: false),
    );
  }

  final List<MemeStickerDefinition> stickers;
  final Map<String, MemeStickerDefinition> _byId;

  MemeStickerDefinition byId(String id) {
    final sticker = _byId[id];
    if (sticker == null) throw ArgumentError.value(id, 'id', 'Unknown sticker');
    return sticker;
  }

  List<MemeStickerDefinition> inCategory(MemeStickerCategory category) =>
      stickers
          .where((item) => item.category == category)
          .toList(growable: false);
}

Future<MemeStickerCatalog> loadMemeStickerCatalog([AssetBundle? bundle]) async {
  final raw = await (bundle ?? rootBundle).loadString(
    'assets/mock/sticker_catalog.json',
  );
  return MemeStickerCatalog.fromJson(jsonDecode(raw) as Map<String, dynamic>);
}

enum StudioImageSource { asset, memory }

final class StudioImageRef {
  const StudioImageRef.asset(String assetPath)
    : source = StudioImageSource.asset,
      path = assetPath,
      bytes = null;

  StudioImageRef.memory(Uint8List value)
    : source = StudioImageSource.memory,
      path = null,
      bytes = Uint8List.fromList(value);

  final StudioImageSource source;
  final String? path;
  final Uint8List? bytes;
}

enum StudioBackgroundKind { image, gradient }

final class StudioBackgroundDefinition {
  const StudioBackgroundDefinition.image({
    required this.id,
    required this.label,
    required this.assetPath,
  }) : kind = StudioBackgroundKind.image,
       colors = const [];

  const StudioBackgroundDefinition.gradient({
    required this.id,
    required this.label,
    required this.colors,
  }) : kind = StudioBackgroundKind.gradient,
       assetPath = null;

  final String id;
  final String label;
  final StudioBackgroundKind kind;
  final String? assetPath;
  final List<Color> colors;
}

abstract final class StudioBackgrounds {
  static const all = <StudioBackgroundDefinition>[
    StudioBackgroundDefinition.image(
      id: 'startup',
      label: 'Sunset',
      assetPath: 'assets/images/backgrounds/startup.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'fitness',
      label: 'Fitness',
      assetPath: 'assets/images/backgrounds/fitness.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'business',
      label: 'Business',
      assetPath: 'assets/images/backgrounds/business.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'technology',
      label: 'Tech',
      assetPath: 'assets/images/backgrounds/technology.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'creative',
      label: 'Creative',
      assetPath: 'assets/images/backgrounds/creative.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'education',
      label: 'Study',
      assetPath: 'assets/images/backgrounds/education.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'career',
      label: 'Career',
      assetPath: 'assets/images/backgrounds/career.jpg',
    ),
    StudioBackgroundDefinition.image(
      id: 'travel',
      label: 'Travel',
      assetPath: 'assets/images/backgrounds/travel.jpg',
    ),
    StudioBackgroundDefinition.gradient(
      id: 'gradient_hot',
      label: 'Hot',
      colors: [Color(0xFFF4066E), Color(0xFFFF8A00)],
    ),
    StudioBackgroundDefinition.gradient(
      id: 'gradient_night',
      label: 'Night',
      colors: [Color(0xFF15102A), Color(0xFF7257FF)],
    ),
    StudioBackgroundDefinition.gradient(
      id: 'gradient_sky',
      label: 'Sky',
      colors: [Color(0xFF315CFF), Color(0xFF00A39A)],
    ),
    StudioBackgroundDefinition.gradient(
      id: 'gradient_candy',
      label: 'Candy',
      colors: [Color(0xFFFF8BC2), Color(0xFF8A6BFF), Color(0xFFFFD84D)],
    ),
  ];

  static StudioBackgroundDefinition byId(String id) =>
      all.singleWhere((item) => item.id == id);
}

final class StickerPlacement {
  const StickerPlacement({
    required this.instanceId,
    required this.stickerId,
    required this.centerX,
    required this.centerY,
    required this.scale,
    required this.rotation,
  });

  static const minimumScale = 0.15;
  static const maximumScale = 0.44;

  final String instanceId;
  final String stickerId;
  final double centerX;
  final double centerY;
  final double scale;
  final double rotation;

  StickerPlacement copyWith({
    double? centerX,
    double? centerY,
    double? scale,
    double? rotation,
  }) => StickerPlacement(
    instanceId: instanceId,
    stickerId: stickerId,
    centerX: centerX ?? this.centerX,
    centerY: centerY ?? this.centerY,
    scale: scale ?? this.scale,
    rotation: rotation ?? this.rotation,
  );
}

final class SocialPostDraft {
  SocialPostDraft({
    required this.message,
    required this.avatar,
    required this.backgroundId,
    required List<StickerPlacement> stickers,
  }) : stickers = List.unmodifiable(stickers);

  final String message;
  final StudioImageRef avatar;
  final String backgroundId;
  final List<StickerPlacement> stickers;

  SocialPostDraft copyWith({
    String? message,
    StudioImageRef? avatar,
    String? backgroundId,
    List<StickerPlacement>? stickers,
  }) => SocialPostDraft(
    message: message ?? this.message,
    avatar: avatar ?? this.avatar,
    backgroundId: backgroundId ?? this.backgroundId,
    stickers: stickers ?? this.stickers,
  );
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Missing non-empty string: $key');
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) throw FormatException('Missing integer: $key');
  return value;
}

double _requiredDouble(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) throw FormatException('Missing number: $key');
  return value.toDouble();
}
