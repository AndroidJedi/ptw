import '../../models/ptw_story_composition.dart';

final class PtwStoryLookPreset {
  const PtwStoryLookPreset({
    required this.id,
    required this.label,
    required this.textTreatment,
    required this.backgroundId,
    this.stickerId,
    this.stickerX = 0.78,
    this.stickerY = 0.24,
  });

  final String id;
  final String label;
  final PtwStoryTextTreatment textTreatment;
  final String? backgroundId;
  final String? stickerId;
  final double stickerX;
  final double stickerY;
}

abstract final class PtwStoryLooks {
  static const all = <PtwStoryLookPreset>[
    PtwStoryLookPreset(
      id: 'project_focus',
      label: 'My photo',
      textTreatment: PtwStoryTextTreatment.clean,
      backgroundId: null,
    ),
    PtwStoryLookPreset(
      id: 'hot_dare',
      label: 'Hot dare',
      textTreatment: PtwStoryTextTreatment.sticker,
      backgroundId: 'gradient_hot',
      stickerId: 'side_eye_orb',
    ),
    PtwStoryLookPreset(
      id: 'night_detective',
      label: 'Night watch',
      textTreatment: PtwStoryTextTreatment.night,
      backgroundId: 'gradient_night',
      stickerId: 'tiny_detective',
      stickerX: 0.22,
      stickerY: 0.72,
    ),
    PtwStoryLookPreset(
      id: 'candy_hype',
      label: 'Candy hype',
      textTreatment: PtwStoryTextTreatment.candy,
      backgroundId: 'gradient_candy',
      stickerId: 'cheering_blob',
    ),
    PtwStoryLookPreset(
      id: 'yellow_chaos',
      label: 'Pure chaos',
      textTreatment: PtwStoryTextTreatment.chaos,
      backgroundId: 'gradient_yellow',
      stickerId: 'screaming_toaster',
      stickerX: 0.76,
      stickerY: 0.72,
    ),
    PtwStoryLookPreset(
      id: 'sky_victory',
      label: 'Victory lap',
      textTreatment: PtwStoryTextTreatment.victory,
      backgroundId: 'gradient_sky',
      stickerId: 'trophy_gremlin',
      stickerX: 0.24,
      stickerY: 0.72,
    ),
  ];

  static PtwStoryLookPreset byId(String id) =>
      all.firstWhere((item) => item.id == id, orElse: () => all.first);

  static int indexForSeed(String value) {
    var hash = 0;
    for (final unit in value.codeUnits) {
      hash = ((hash * 31) + unit) & 0x7fffffff;
    }
    return hash % all.length;
  }

  static PtwStoryComposition apply(
    PtwStoryComposition composition,
    PtwStoryLookPreset preset,
    DateTime updatedAt,
  ) {
    final sticker = preset.stickerId;
    return composition.copyWith(
      backgroundId: preset.backgroundId,
      clearBackgroundId: preset.backgroundId == null,
      lookId: preset.id,
      textTreatment: preset.textTreatment,
      stickers:
          sticker == null
              ? const []
              : [
                PtwStoryStickerPlacement(
                  instanceId: 'preset_${preset.id}',
                  stickerId: sticker,
                  centerX: preset.stickerX,
                  centerY: preset.stickerY,
                  scale: 0.23,
                  rotation: 0,
                ),
              ],
      updatedAt: updatedAt,
    );
  }
}
