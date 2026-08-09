import '../../features/share/share_models.dart';
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
  }) => const PtwStoryComposer()
      .create(project: project, event: event, momentId: momentId, now: now)
      .copyWith(
        clearBackgroundId: true,
        lookId: 'soft_focus_1',
        textTreatment: PtwStoryTextTreatment.clean,
        stickers: const [],
      );

  ShareEditorContent content({
    required PtwProject project,
    required PtwStoryComposition composition,
  }) => ShareEditorContent(
    projectId: project.id,
    headline: composition.headline,
    secondaryText: composition.dare,
    ownerName: project.ownerName,
    ownerHandle: project.ownerHandle,
    avatar: _image(composition.avatar),
    cover: _image(composition.projectBackground),
    caption: composition.caption,
    publicLink: composition.publicLink,
    previousMedia: _image(composition.projectBackground),
    currentMedia: _image(composition.projectBackground),
    progressValue:
        project.status == PtwProjectStatus.completed ? '100%' : 'IN PROGRESS',
    metricValue:
        project.status == PtwProjectStatus.completed
            ? 'GOAL COMPLETED'
            : 'STILL SHOWING UP',
    previousTimeLabel: 'BEFORE',
    currentTimeLabel: 'NOW',
    proofLabel: composition.eventName,
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
  }) {
    final encoded = composition.editorValue;
    if (encoded != null &&
        composition.themeId == theme.id &&
        composition.themeSchemaVersion <= theme.schemaVersion) {
      try {
        final restored = ShareEditorValue.fromJson(encoded);
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
        theme.looks.any((item) => item.id == composition.lookId)
            ? composition.lookId
            : _lookForTreatment(composition.textTreatment, theme);
    final look = theme.look(lookId);
    final knownStickerIds = theme.stickers.map((item) => item.id).toSet();
    return ShareEditorValue(
      lookId: look.id,
      templateId: theme.defaultTemplateId,
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
        for (final item in composition.stickers)
          if (knownStickerIds.contains(item.stickerId))
            ShareStickerValue(
              instanceId: item.instanceId,
              stickerId: item.stickerId,
              centerX: item.centerX,
              centerY: item.centerY,
              scale: item.scale,
              rotation: item.rotation,
            ),
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
    );
  }

  ShareImageValue _image(PtwImageRef image) => switch (image.source) {
    PtwImageSource.asset => ShareImageValue.asset(image.path),
    PtwImageSource.file => ShareImageValue.file(image.path),
  };

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

  PtwStoryTextTreatment _treatmentForLook(String lookId) {
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
