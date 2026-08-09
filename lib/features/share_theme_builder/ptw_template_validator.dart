import '../../generated_share_editor/src/share_theme.dart';

enum PtwValidationSeverity { error, warning, note }

final class PtwValidationIssue {
  const PtwValidationIssue({
    required this.code,
    required this.message,
    required this.severity,
  });

  final String code;
  final String message;
  final PtwValidationSeverity severity;
}

final class PtwTemplateValidation {
  const PtwTemplateValidation({
    required this.template,
    required this.issues,
    required this.score,
  });

  final ShareTemplateConfig template;
  final List<PtwValidationIssue> issues;
  final int score;

  bool get isReady =>
      !issues.any((issue) => issue.severity == PtwValidationSeverity.error);
  int get errorCount =>
      issues
          .where((issue) => issue.severity == PtwValidationSeverity.error)
          .length;
  int get warningCount =>
      issues
          .where((issue) => issue.severity == PtwValidationSeverity.warning)
          .length;
}

abstract final class PtwTemplateValidator {
  static PtwTemplateValidation validate(
    ShareThemeConfig theme,
    ShareTemplateConfig template,
  ) {
    final issues = <PtwValidationIssue>[];

    void issue(
      String code,
      String message, {
      PtwValidationSeverity severity = PtwValidationSeverity.error,
    }) => issues.add(
      PtwValidationIssue(code: code, message: message, severity: severity),
    );

    const requiredFamilies = {
      ShareTemplateFamily.heroPhoto,
      ShareTemplateFamily.comparison,
      ShareTemplateFamily.progress,
      ShareTemplateFamily.documentary,
      ShareTemplateFamily.conflict,
      ShareTemplateFamily.milestone,
      ShareTemplateFamily.proof,
    };
    final production = theme.templates.where(
      (item) => item.status == ShareTemplateStatus.production,
    );
    final missingFamilies = requiredFamilies.difference(
      production.map((item) => item.family).toSet(),
    );
    if (missingFamilies.isNotEmpty) {
      issue(
        'theme_families',
        'The production theme is missing ${missingFamilies.length} PTW family or families.',
      );
    }
    for (final journey in ShareJourneyState.values) {
      if (journey == ShareJourneyState.unassigned) continue;
      final familyCount =
          production
              .where((item) => item.supportedJourneyStates.contains(journey))
              .map((item) => item.family)
              .toSet()
              .length;
      if (familyCount < 3) {
        issue(
          'journey_coverage_${journey.name}',
          '${journey.label} needs at least three production template families.',
        );
      }
    }
    if (theme.maximumStickerCount > 3 || theme.maximumDecorationCount > 3) {
      issue(
        'sticker_limit',
        'Runtime themes may expose at most three stickers.',
      );
    }

    if (template.family == ShareTemplateFamily.unassigned) {
      issue('family', 'Choose a PTW template family.');
    }
    if (template.primaryJourneyState == ShareJourneyState.unassigned) {
      issue('journey', 'Choose a primary journey state.');
    }
    if (!template.supportedJourneyStates.contains(
      template.primaryJourneyState,
    )) {
      issue('journey_support', 'Primary journey state must be supported.');
    }
    if (template.primaryAnchor == ShareSemanticRole.unassigned) {
      issue('anchor', 'Choose the template’s primary semantic anchor.');
    }
    if (!template.requiredContentRoles.contains(template.primaryAnchor) &&
        !template.optionalContentRoles.contains(template.primaryAnchor)) {
      issue(
        'anchor_role',
        'Primary anchor must be declared as a content role.',
      );
    }

    final visible = <ShareLayerConfig>[];
    for (final layer in theme.layers) {
      final override = template.layerOverrides[layer.id];
      final isVisible = override?['visible'] as bool? ?? layer.visible;
      if (isVisible) {
        final overrideStyle = override?['style'];
        final rawTransform = override?['transform'];
        final rawEmphasis = override?['emphasis'];
        visible.add(
          layer.copyWith(
            transform:
                rawTransform is Map<String, dynamic>
                    ? ShareLayerTransform.fromJson(rawTransform)
                    : layer.transform,
            emphasis:
                rawEmphasis is String
                    ? ShareLayerEmphasis.values.firstWhere(
                      (item) => item.name == rawEmphasis,
                      orElse: () => layer.emphasis,
                    )
                    : layer.emphasis,
            style: {
              ...layer.style,
              if (overrideStyle is Map<String, dynamic>) ...overrideStyle,
              if (overrideStyle is Map<String, Object?>) ...overrideStyle,
            },
          ),
        );
      }
    }
    final visibleRoles = visible.map((layer) => layer.semanticRole).toSet();
    for (final role in template.requiredContentRoles) {
      if (!visibleRoles.contains(role)) {
        issue(
          'required_${role.name}',
          'Required role “${_label(role.name)}” has no visible layer.',
        );
      }
    }
    if (!visibleRoles.contains(ShareSemanticRole.brand)) {
      issue('brand', 'A visible PTW brand layer is required.');
    }
    if (!visibleRoles.contains(ShareSemanticRole.headline)) {
      issue('headline', 'A visible headline layer is required.');
    }

    final primaryCount =
        visible
            .where((layer) => layer.emphasis == ShareLayerEmphasis.primary)
            .length;
    if (primaryCount != 1) {
      issue(
        'emphasis',
        'Use one dominant primary-emphasis layer; found $primaryCount.',
      );
    }

    if (template.family == ShareTemplateFamily.comparison ||
        template.supportsComparison) {
      if (template.supportedMediaCount < 2 ||
          !visibleRoles.contains(ShareSemanticRole.previousMedia) ||
          !visibleRoles.contains(ShareSemanticRole.currentMedia)) {
        issue(
          'comparison_media',
          'Comparison templates need visible previous/current media and a media count of at least two.',
        );
      }
    }
    if (template.family == ShareTemplateFamily.progress &&
        !visibleRoles.contains(ShareSemanticRole.progress)) {
      issue(
        'progress_role',
        'Progress templates need a visible progress role.',
      );
    }
    if (template.supportsProof &&
        !visibleRoles.intersection({
          ShareSemanticRole.proof,
          ShareSemanticRole.metric,
          ShareSemanticRole.progress,
          ShareSemanticRole.previousMedia,
          ShareSemanticRole.currentMedia,
        }).isNotEmpty) {
      issue('proof', 'Proof support needs a visible proof or evidence role.');
    }

    if (template.mediaCoverage < 0.7 || template.mediaCoverage > 0.9) {
      issue(
        'media_coverage',
        'User media must occupy 70–90% of the fixed composition.',
      );
    }
    if (template.accentColorToken.trim().isEmpty) {
      issue('accent_token', 'Declare exactly one PTW accent color token.');
    }

    final editable = visible.where(
      (layer) => layer.runtimePermissions.canEditContent,
    );
    if (editable.length > 5) {
      issue(
        'editable_fields',
        'A template may declare at most five editable fields.',
      );
    }
    if (editable.any(
      (layer) => layer.semanticRole != ShareSemanticRole.headline,
    )) {
      issue(
        'runtime_copy',
        'The public runtime may edit only the optional headline.',
      );
    }

    const countedTypographyRoles = {
      ShareSemanticRole.headline,
      ShareSemanticRole.challenge,
      ShareSemanticRole.criticism,
      ShareSemanticRole.proof,
      ShareSemanticRole.metric,
      ShareSemanticRole.progress,
      ShareSemanticRole.goal,
    };
    final typography = visible.where(
      (layer) =>
          layer.type == 'text' &&
          countedTypographyRoles.contains(layer.semanticRole),
    );
    final fontSizes =
        typography
            .map((layer) => layer.style['fontSize'])
            .whereType<num>()
            .map((value) => value.toDouble())
            .toSet();
    final fontWeights =
        typography
            .map((layer) => layer.style['fontWeight'])
            .whereType<num>()
            .map((value) => value.toInt())
            .toSet();
    if (fontSizes.length > 2 || fontWeights.length > 2) {
      issue(
        'typography_limit',
        'Visible content may use at most two font sizes and two weights.',
      );
    }

    final brandLayers = visible.where(
      (layer) => layer.semanticRole == ShareSemanticRole.brand,
    );
    final canvasArea = theme.canvas.width * theme.canvas.height;
    if (brandLayers.any(
      (layer) =>
          layer.transform.width * layer.transform.height / canvasArea > 0.05,
    )) {
      issue(
        'logo_size',
        'The PTW logo footprint must remain under 5% of the canvas.',
      );
    }

    final animation = template.animation;
    if (animation.delayMilliseconds < 0 ||
        animation.durationMilliseconds <= 0 ||
        animation.easing.trim().isEmpty) {
      issue('animation', 'Export valid fixed animation metadata.');
    }

    const requiredZones = {
      ShareSafeZoneKind.instagramTopDanger,
      ShareSafeZoneKind.instagramBottomDanger,
      ShareSafeZoneKind.recommendedLink,
      ShareSafeZoneKind.protectedSubject,
      ShareSafeZoneKind.brandSafe,
    };
    final zoneKinds = template.safeZones.map((zone) => zone.kind).toSet();
    final missingZones = requiredZones.difference(zoneKinds);
    if (missingZones.isNotEmpty) {
      issue(
        'safe_zones',
        'Add ${missingZones.length} missing PTW safe-zone guide(s).',
      );
    }

    for (final layer in visible.where((item) => item.type == 'text')) {
      final style = layer.style;
      final family = style['fontFamily'];
      if (family is String && !family.startsWith('Ptw')) {
        issue(
          'font_${layer.id}',
          '${layer.label} uses a font outside the PTW design system.',
        );
      }
      final size = style['fontSize'];
      if (size is num && size > 86) {
        issue(
          'scale_${layer.id}',
          '${layer.label} exceeds the recommended maximum type scale.',
          severity: PtwValidationSeverity.warning,
        );
      }
    }

    final runtime = template.runtimePermissions;
    if (runtime.userCanCropMedia && !runtime.userCanReplaceMedia) {
      issue(
        'runtime_crop',
        'Crop permission should be paired with replace-media permission.',
        severity: PtwValidationSeverity.warning,
      );
    }
    if (runtime.userCanEditHeadline &&
        !visible.any(
          (layer) =>
              layer.semanticRole == ShareSemanticRole.headline &&
              layer.runtimePermissions.canEditContent,
        )) {
      issue(
        'runtime_headline',
        'Headline editing is enabled, but no visible headline layer permits it.',
      );
    }
    if (runtime.userCanEditProofValue &&
        !visible.any(
          (layer) =>
              {
                ShareSemanticRole.proof,
                ShareSemanticRole.metric,
                ShareSemanticRole.progress,
              }.contains(layer.semanticRole) &&
              layer.runtimePermissions.canEditContent,
        )) {
      issue(
        'runtime_proof',
        'Proof editing is enabled, but no visible proof layer permits it.',
      );
    }
    if (template.status == ShareTemplateStatus.experimental) {
      issue(
        'experimental',
        'Template is marked experimental.',
        severity: PtwValidationSeverity.note,
      );
    }

    final errorCount =
        issues
            .where((item) => item.severity == PtwValidationSeverity.error)
            .length;
    final warningCount =
        issues
            .where((item) => item.severity == PtwValidationSeverity.warning)
            .length;
    final score = (100 - errorCount * 18 - warningCount * 5).clamp(0, 100);
    return PtwTemplateValidation(
      template: template,
      issues: List.unmodifiable(issues),
      score: score,
    );
  }

  static List<PtwTemplateValidation> validateTheme(ShareThemeConfig theme) => [
    for (final template in theme.templates) validate(theme, template),
  ];

  static String _label(String value) =>
      value
          .replaceAllMapped(RegExp(r'([A-Z])'), (match) => ' ${match.group(1)}')
          .trim()
          .toLowerCase();
}
