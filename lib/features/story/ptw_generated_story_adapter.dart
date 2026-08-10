import '../../features/share/share_models.dart';
import '../../features/share/share_generation.dart';
import '../../features/social_post_studio/ptw_story_composer.dart';
import '../../generated_share_editor/generated_share_editor.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_story_composition.dart';

final class PtwGeneratedStoryAdapter {
  const PtwGeneratedStoryAdapter();

  PtwStoryComposition createBase({
    required PtwProject project,
    required ShareEvent event,
    required DateTime now,
    String? momentId,
    ShareCandidate? candidate,
  }) => const PtwStoryComposer()
      .create(project: project, event: event, momentId: momentId, now: now)
      .copyWith(
        clearBackgroundId: true,
        headline: candidate?.headline,
        dare: candidate?.secondaryText,
        lookId: candidate?.lookId ?? 'soft_focus_1',
        textTreatment: _treatmentForLook(candidate?.lookId ?? 'soft_focus_1'),
        stickers: const [],
        journeyState: candidate?.journeyState.name,
        candidateId: candidate?.id,
        familyId: candidate?.family.name,
        templateId: candidate?.templateId,
        regenerationIndex: candidate?.regenerationIndex,
        progressFraction:
            candidate?.progressFraction ?? project.progressMetric?.fraction,
      );

  ShareEditorContent content({
    required PtwProject project,
    required PtwStoryComposition composition,
    ShareCandidate? candidate,
  }) => ShareEditorContent(
    projectId: project.id,
    headline: candidate?.headline ?? composition.headline,
    secondaryText: candidate?.secondaryText ?? composition.dare,
    ownerName: project.ownerName,
    ownerHandle: project.ownerHandle,
    avatar: _image(composition.avatar),
    cover: _image(candidate?.currentMedia ?? composition.projectBackground),
    caption: composition.caption,
    publicLink: composition.publicLink,
    previousMedia:
        candidate?.previousMedia == null
            ? null
            : _image(candidate!.previousMedia!),
    currentMedia: candidate == null ? null : _image(candidate.currentMedia),
    progressValue:
        candidate?.progressValue ?? project.progressMetric?.progressLabel,
    metricValue: candidate?.metricValue ?? project.progressMetric?.currentLabel,
    previousTimeLabel: candidate?.previousTimeLabel ?? 'BEFORE',
    currentTimeLabel: candidate?.currentTimeLabel ?? 'NOW',
    proofLabel: candidate?.proofLabel ?? composition.eventName,
    custom: {
      'eventName': composition.eventName,
      'momentId': composition.momentId,
      if (project.deadline != null)
        'deadline': project.deadline!.toIso8601String(),
    },
  );

  ShareEditorValue value({
    required ShareThemeConfig theme,
    required ShareEditorContent content,
    required PtwStoryComposition composition,
    required PtwProject project,
    ShareCandidate? candidate,
  }) {
    final encoded = composition.editorValue;
    if (encoded != null &&
        composition.themeId == theme.id &&
        composition.themeSchemaVersion <= theme.schemaVersion) {
      try {
        final restored = _migrateSavedValue(
          theme: theme,
          value: ShareEditorValue.fromJson(encoded),
          candidate: candidate,
        );
        final validator = ShareEditorController(
          theme: theme,
          content: content,
          initialValue: restored,
          entitlements: (_) => true,
        );
        final migrated = validator.value;
        validator.dispose();
        return migrated;
      } on Object {
        // Fall through to the legacy fixed-layout migration.
      }
    }
    final lookId =
        candidate?.lookId ??
        (theme.looks.any((item) => item.id == composition.lookId)
            ? composition.lookId
            : _lookForTreatment(composition.textTreatment, theme));
    final look = theme.look(lookId);
    final knownStickerIds = theme.stickers.map((item) => item.id).toSet();
    return ShareEditorValue(
      lookId: look.id,
      templateId:
          candidate?.templateId ??
          (composition.templateId != null &&
                  theme.templates.any(
                    (item) => item.id == composition.templateId,
                  )
              ? composition.templateId
              : theme.defaultTemplateId),
      backgroundId:
          composition.backgroundId == null
              ? 'project_cover'
              : theme.backgrounds.any(
                (item) => item.id == composition.backgroundId,
              )
              ? composition.backgroundId
              : look.backgroundId ?? theme.defaultBackgroundId,
      layerValues: {
        'headline': composition.headline,
        'secondary': composition.dare,
        'avatar': _image(composition.avatar),
        'brand': 'PTW',
        'tagline': 'PROVE THEM WRONG',
      },
      transforms: const {},
      backgroundEdit: look.backgroundTreatment,
      stickers: [
        for (final item
            in composition.stickers.isNotEmpty
                ? composition.stickers.map(
                  (item) => ShareStickerValue(
                    instanceId: item.instanceId,
                    stickerId: item.stickerId,
                    centerX: item.centerX,
                    centerY: item.centerY,
                    scale: item.scale,
                    rotation: item.rotation,
                  ),
                )
                : candidate?.stickersAllowed == true
                ? _semanticStickers(
                  project.category ?? PtwProjectCategory.other,
                  candidate!,
                ).take(theme.maximumStickerCount)
                : const <ShareStickerValue>[])
          if (knownStickerIds.contains(item.stickerId)) item,
      ],
    );
  }

  PtwStoryComposition composition({
    required ShareThemeConfig theme,
    required PtwStoryComposition base,
    required ShareEditorValue value,
    required DateTime updatedAt,
  }) {
    final headline = '${value.layerValues['headline'] ?? base.headline}'.trim();
    final dare = '${value.layerValues['secondary'] ?? base.dare}'.trim();
    final templateId = value.templateId ?? base.templateId;
    return PtwStoryComposition(
      projectId: base.projectId,
      eventName: base.eventName,
      momentId: base.momentId,
      headline: headline,
      dare: dare,
      avatar: base.avatar,
      projectBackground: base.projectBackground,
      backgroundId:
          value.backgroundId == 'project_cover' ? null : value.backgroundId,
      lookId: value.lookId,
      textTreatment: _treatmentForLook(value.lookId),
      stickers: [
        for (final item in value.stickers)
          PtwStoryStickerPlacement(
            instanceId: item.instanceId,
            stickerId: item.stickerId,
            centerX: item.centerX,
            centerY: item.centerY,
            scale: item.scale,
            rotation: item.rotation,
          ),
      ],
      caption: '$headline\n$dare',
      themeId: theme.id,
      themeSchemaVersion: theme.schemaVersion,
      editorValue: value.toJson(),
      createdAt: base.createdAt,
      updatedAt: updatedAt,
      journeyState: base.journeyState,
      candidateId: base.candidateId,
      familyId:
          templateId == null
              ? base.familyId
              : theme.template(templateId).family.name,
      templateId: templateId,
      regenerationIndex: base.regenerationIndex,
      progressFraction: base.progressFraction,
    );
  }

  ShareImageValue _image(PtwImageRef image) => switch (image.source) {
    PtwImageSource.asset => ShareImageValue.asset(image.path),
    PtwImageSource.file => ShareImageValue.file(image.path),
  };

  /// Moves a saved composition onto the current fixed-layout schema while
  /// retaining the two public edits that v1 promises to preserve: headline and
  /// photo/crop. Obsolete free-form transforms and style controls deliberately
  /// fall back to the selected look and template.
  ShareEditorValue _migrateSavedValue({
    required ShareThemeConfig theme,
    required ShareEditorValue value,
    ShareCandidate? candidate,
  }) {
    final knownLooks = theme.looks.map((item) => item.id).toSet();
    final knownTemplates = theme.templates.map((item) => item.id).toSet();
    final knownBackgrounds = theme.backgrounds.map((item) => item.id).toSet();
    final knownLayers = theme.layers.map((item) => item.id).toSet();
    final knownStickers = theme.stickers.map((item) => item.id).toSet();
    final templateIsObsolete =
        value.templateId == null || !knownTemplates.contains(value.templateId);
    final templateId =
        candidate != null && knownTemplates.contains(candidate.templateId)
            ? candidate.templateId
            : templateIsObsolete
            ? theme.defaultTemplateId
            : value.templateId!;
    final lookId =
        candidate != null && knownLooks.contains(candidate.lookId)
            ? candidate.lookId
            : knownLooks.contains(value.lookId)
            ? value.lookId
            : theme.defaultLookId;
    final backgroundId =
        value.backgroundId != null &&
                knownBackgrounds.contains(value.backgroundId)
            ? value.backgroundId
            : knownBackgrounds.contains('project_cover')
            ? 'project_cover'
            : theme.defaultBackgroundId;
    final stickerIds = <String>{};
    final stickers = <ShareStickerValue>[];
    for (final item in value.stickers) {
      if (stickers.length == theme.maximumStickerCount ||
          !knownStickers.contains(item.stickerId) ||
          !stickerIds.add(item.instanceId)) {
        continue;
      }
      final config = theme.sticker(item.stickerId);
      if (item.centerX < 0 ||
          item.centerX > 1 ||
          item.centerY < 0 ||
          item.centerY > 1 ||
          item.scale < config.minimumScale ||
          item.scale > config.maximumScale) {
        continue;
      }
      stickers.add(item);
    }
    double finiteClamp(
      double value,
      double minimum,
      double maximum,
      double fallback,
    ) => value.isFinite ? value.clamp(minimum, maximum) : fallback;
    String validColor(String value, String fallback) =>
        RegExp(r'^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$').hasMatch(value)
            ? (value.startsWith('#') ? value : '#$value')
            : fallback;
    final backgroundEdit = value.backgroundEdit.copyWith(
      alignmentX: finiteClamp(value.backgroundEdit.alignmentX, -1, 1, 0),
      alignmentY: finiteClamp(value.backgroundEdit.alignmentY, -1, 1, 0),
      zoom: finiteClamp(value.backgroundEdit.zoom, 1, 4, 1),
      imageOpacity: finiteClamp(value.backgroundEdit.imageOpacity, 0.2, 1, 1),
      blur: finiteClamp(value.backgroundEdit.blur, 0, 30, 0),
      brightness: finiteClamp(value.backgroundEdit.brightness, -1, 1, 0),
      contrast: finiteClamp(value.backgroundEdit.contrast, 0.5, 2, 1),
      saturation: finiteClamp(value.backgroundEdit.saturation, 0, 2, 1),
      tintColor: validColor(value.backgroundEdit.tintColor, '#FFFFFFFF'),
      tintOpacity: finiteClamp(value.backgroundEdit.tintOpacity, 0, 1, 0),
      overlayColor: validColor(value.backgroundEdit.overlayColor, '#FF000000'),
      overlayOpacity: finiteClamp(value.backgroundEdit.overlayOpacity, 0, 1, 0),
      textureColor: validColor(value.backgroundEdit.textureColor, '#FFFFFFFF'),
      textureSecondaryColor: validColor(
        value.backgroundEdit.textureSecondaryColor,
        '#FFBFF7FF',
      ),
      textureIntensity: finiteClamp(
        value.backgroundEdit.textureIntensity,
        0,
        1,
        0,
      ),
      textureScale: finiteClamp(value.backgroundEdit.textureScale, 0.5, 4, 1),
    );
    return value.copyWith(
      lookId: lookId,
      templateId: templateId,
      backgroundId: backgroundId,
      backgroundEdit: backgroundEdit,
      layerValues: {
        for (final entry in value.layerValues.entries)
          if (knownLayers.contains(entry.key)) entry.key: entry.value,
      },
      transforms:
          templateIsObsolete
              ? const {}
              : {
                for (final entry in value.transforms.entries)
                  if (knownLayers.contains(entry.key) &&
                      entry.value.width > 0 &&
                      entry.value.height > 0 &&
                      entry.value.x >= 0 &&
                      entry.value.y >= 0 &&
                      entry.value.x + entry.value.width <=
                          theme.canvas.width + 0.001 &&
                      entry.value.y + entry.value.height <=
                          theme.canvas.height + 0.001)
                    entry.key: entry.value,
              },
      stickers: stickers,
      overlays: const [],
      propertyOverrides: const {},
    );
  }

  List<ShareStickerValue> _semanticStickers(
    PtwProjectCategory category,
    ShareCandidate candidate,
  ) {
    final offset = candidate.regenerationIndex % 3;
    const slots = [
      (centerX: 0.81, centerY: 0.2, rotation: 0.1),
      (centerX: 0.18, centerY: 0.72, rotation: -0.08),
      (centerX: 0.82, centerY: 0.73, rotation: 0.06),
    ];
    return [
      for (var index = 0; index < 3; index++)
        ShareStickerValue(
          instanceId: 'semantic_${category.name}_${index + 1}',
          stickerId: 'category_${category.name}_${((index + offset) % 3) + 1}',
          centerX: slots[index].centerX,
          centerY: slots[index].centerY,
          scale: 0.18,
          rotation: slots[index].rotation,
        ),
    ];
  }

  String _lookForTreatment(
    PtwStoryTextTreatment treatment,
    ShareThemeConfig theme,
  ) {
    final candidate = switch (treatment) {
      PtwStoryTextTreatment.clean => 'soft_focus_1',
      PtwStoryTextTreatment.sticker => 'pixel_pop_1',
      PtwStoryTextTreatment.night => 'static_note_1',
      PtwStoryTextTreatment.candy => 'holo_crush_1',
      PtwStoryTextTreatment.chaos => 'peach_collage_1',
      PtwStoryTextTreatment.victory => 'legacy_victory_1',
    };
    return theme.looks.any((item) => item.id == candidate)
        ? candidate
        : theme.defaultLookId;
  }

  static PtwStoryTextTreatment _treatmentForLook(String lookId) {
    if (lookId.startsWith('pixel_pop_') || lookId == 'hot_dare') {
      return PtwStoryTextTreatment.sticker;
    }
    if (lookId.startsWith('static_note_') || lookId == 'night_detective') {
      return PtwStoryTextTreatment.night;
    }
    if (lookId.startsWith('holo_crush_') || lookId == 'candy_hype') {
      return PtwStoryTextTreatment.candy;
    }
    if (lookId.startsWith('peach_collage_') || lookId == 'yellow_chaos') {
      return PtwStoryTextTreatment.chaos;
    }
    if (lookId.startsWith('legacy_victory_') || lookId == 'sky_victory') {
      return PtwStoryTextTreatment.victory;
    }
    return PtwStoryTextTreatment.clean;
  }
}
