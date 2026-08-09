import 'dart:convert';
import 'dart:io';

import '../features/share_theme_builder/ptw_template_validator.dart';
import '../generated_share_editor/src/share_theme.dart';

const ptwTemplateGeneratorProtocolVersion = '1.0.0';

const ptwTemplateGeneratorInstructions = '''
Author PTW schema-v3 templates only. Call get_template_context before drafting, validate_template while iterating, and upsert_template only after validation succeeds and the user has requested installation. Use only existing layer, asset, background, sticker, and look IDs. Never emit or install Dart code or external assets. Export/sync the runtime theme before Flutter runs.
''';

const ptwTemplateGeneratorContract = '''
# PTW template generator MCP contract

The server authors schema-v3 `ShareTemplateConfig` objects for PTW's compiled
Flutter renderer. Templates may compose existing catalog layers; they may not
add Dart source, assets, backgrounds, stickers, looks, or external references.

## Workflow

1. Call `get_template_context`, optionally filtered by family or journey state.
2. Draft a complete production template with a new ID/version or the next
   version of an existing template.
3. Call `validate_template` until `valid` is true.
4. Call `upsert_template` with the latest `catalogRevision`.
5. Run the pre-run sync client so the Flutter asset matches the catalog.

## Tools

- `get_template_context({family?, journeyState?})` is read-only.
- `validate_template({template})` is read-only and never changes the catalog.
- `upsert_template({template, expectedCatalogRevision})` atomically updates the
  canonical catalog. Validation errors and stale revisions never write.
- `export_runtime_theme({})` returns the normalized catalog used by the sync
  client.

All successful tool payloads are JSON objects in both structured content and a
text fallback. Warnings are non-blocking; errors block installation and sync.
''';

final class PtwCatalogIssue {
  const PtwCatalogIssue({
    required this.code,
    required this.message,
    required this.severity,
    this.templateId,
  });

  final String code;
  final String message;
  final PtwValidationSeverity severity;
  final String? templateId;

  Map<String, dynamic> toJson() => {
    'code': code,
    'message': message,
    'severity': severity.name,
    if (templateId != null) 'templateId': templateId,
  };
}

final class PtwTemplateCatalogSnapshot {
  const PtwTemplateCatalogSnapshot({
    required this.theme,
    required this.normalizedJson,
    required this.revision,
  });

  final ShareThemeConfig theme;
  final String normalizedJson;
  final String revision;
}

final class PtwTemplateProposalValidation {
  const PtwTemplateProposalValidation({
    required this.catalogRevision,
    required this.issues,
    required this.score,
    this.normalizedTemplate,
    this.mergedTheme,
  });

  final String catalogRevision;
  final List<PtwCatalogIssue> issues;
  final int score;
  final ShareTemplateConfig? normalizedTemplate;
  final ShareThemeConfig? mergedTheme;

  bool get isValid =>
      normalizedTemplate != null &&
      mergedTheme != null &&
      !issues.any((issue) => issue.severity == PtwValidationSeverity.error);

  Map<String, dynamic> toJson() => {
    'protocolVersion': ptwTemplateGeneratorProtocolVersion,
    'valid': isValid,
    'catalogRevision': catalogRevision,
    'score': score,
    if (normalizedTemplate != null)
      'normalizedTemplate': normalizedTemplate!.toJson(),
    'issues': issues.map((issue) => issue.toJson()).toList(),
  };
}

final class PtwTemplateCatalog {
  PtwTemplateCatalog(this.catalogFile);

  final File catalogFile;

  static const allowedTemplateKeys = {
    'id',
    'label',
    'family',
    'variant',
    'narrativeIntent',
    'primaryJourneyState',
    'supportedJourneyStates',
    'requiredContentRoles',
    'optionalContentRoles',
    'runtimePermissions',
    'primaryAnchor',
    'supportedMediaCount',
    'supportsComparison',
    'supportsProof',
    'safeZones',
    'designSystemVersion',
    'templateVersion',
    'status',
    'layerOverrides',
    'animation',
    'accentColorToken',
    'mediaCoverage',
  };

  static const allowedLayerOverrideKeys = {
    'visible',
    'transform',
    'emphasis',
    'style',
  };

  static const allowedLayerStyleKeys = {
    'fontSize',
    'minFontSize',
    'maxLines',
  };

  Future<PtwTemplateCatalogSnapshot> load() async {
    if (!await catalogFile.exists()) {
      throw StateError('PTW template catalog not found: ${catalogFile.path}');
    }
    final theme = ShareThemeBundle.fromJsonString(
      await catalogFile.readAsString(),
    );
    final normalizedJson = _normalizedThemeJson(theme);
    return PtwTemplateCatalogSnapshot(
      theme: theme,
      normalizedJson: normalizedJson,
      revision: _revision(normalizedJson),
    );
  }

  Future<Map<String, dynamic>> context({
    String? family,
    String? journeyState,
  }) async {
    final snapshot = await load();
    final theme = snapshot.theme;
    final templates = theme.templates.where((template) {
      if (family != null && template.family.name != family) return false;
      if (journeyState != null &&
          !template.supportedJourneyStates.any(
            (state) => state.name == journeyState,
          )) {
        return false;
      }
      return true;
    });

    return {
      'protocolVersion': ptwTemplateGeneratorProtocolVersion,
      'schemaVersion': theme.schemaVersion,
      'designSystemVersion': theme.designSystemVersion,
      'themeId': theme.id,
      'catalogRevision': snapshot.revision,
      'canvas': theme.canvas.toJson(),
      'families': ShareTemplateFamily.values
          .where((item) => item != ShareTemplateFamily.unassigned)
          .map((item) => item.name)
          .toList(),
      'journeyStates': ShareJourneyState.values
          .where((item) => item != ShareJourneyState.unassigned)
          .map((item) => item.name)
          .toList(),
      'semanticRoles': ShareSemanticRole.values
          .where((item) => item != ShareSemanticRole.unassigned)
          .map((item) => item.name)
          .toList(),
      'layerEmphasisValues': ShareLayerEmphasis.values
          .map((item) => item.name)
          .toList(),
      'animationPresets': ShareAnimationPreset.values
          .map((item) => item.name)
          .toList(),
      'constraints': {
        'templateStatus': ShareTemplateStatus.production.name,
        'newTemplateVersion': 1,
        'replacementVersionRule': 'existing templateVersion + 1',
        'allowedTemplateKeys': allowedTemplateKeys.toList()..sort(),
        'allowedLayerOverrideKeys': allowedLayerOverrideKeys.toList()..sort(),
        'allowedLayerStyleKeys': allowedLayerStyleKeys.toList()..sort(),
        'requiredSafeZoneKinds': ShareSafeZoneKind.values
            .map((item) => item.name)
            .toList(),
        'externalAssetsAllowed': false,
        'dartCodeAllowed': false,
      },
      'catalogIds': {
        'assets': theme.assets.map((item) => item.id).toList(),
        'backgrounds': theme.backgrounds.map((item) => item.id).toList(),
        'stickers': theme.stickers.map((item) => item.id).toList(),
        'looks': theme.looks.map((item) => item.id).toList(),
      },
      'layers': [
        for (final layer in theme.layers)
          {
            'id': layer.id,
            'label': layer.label,
            'type': layer.type,
            'binding': layer.binding,
            'semanticRole': layer.semanticRole.name,
            'emphasis': layer.emphasis.name,
            'visible': layer.visible,
            'transform': layer.transform.toJson(),
            'style': layer.style,
            'runtimePermissions': layer.runtimePermissions.toJson(),
          },
      ],
      'templates': templates.map((item) => item.toJson()).toList(),
    };
  }

  Future<PtwTemplateProposalValidation> validateTemplate(
    Map<String, dynamic> rawTemplate,
  ) async {
    final snapshot = await load();
    return validateTemplateAgainst(snapshot, rawTemplate);
  }

  PtwTemplateProposalValidation validateTemplateAgainst(
    PtwTemplateCatalogSnapshot snapshot,
    Map<String, dynamic> rawTemplate,
  ) {
    final issues = <PtwCatalogIssue>[
      ..._validateAuthoringSurface(snapshot.theme, rawTemplate),
    ];
    ShareTemplateConfig? normalizedTemplate;
    ShareThemeConfig? mergedTheme;
    var score = 0;

    try {
      normalizedTemplate = ShareTemplateConfig.fromJson(rawTemplate);
      issues.addAll(
        _validateVersion(snapshot.theme, normalizedTemplate),
      );
      final source = _deepCopy(snapshot.theme.toJson());
      final templates = (source['templates'] as List<dynamic>)
          .cast<Map<String, dynamic>>();
      final index = templates.indexWhere(
        (template) => template['id'] == normalizedTemplate!.id,
      );
      if (index == -1) {
        templates.add(normalizedTemplate.toJson());
      } else {
        templates[index] = normalizedTemplate.toJson();
      }
      mergedTheme = ShareThemeConfig.fromJson(source);
      final validations = PtwTemplateValidator.validateTheme(mergedTheme);
      final proposalValidation = validations.firstWhere(
        (validation) => validation.template.id == normalizedTemplate!.id,
      );
      score = proposalValidation.score;
      for (final validation in validations) {
        for (final issue in validation.issues) {
          issues.add(
            PtwCatalogIssue(
              code: issue.code,
              message: issue.message,
              severity: issue.severity,
              templateId: validation.template.id,
            ),
          );
        }
      }
    } on Object catch (error) {
      issues.add(
        PtwCatalogIssue(
          code: 'schema',
          message: error.toString(),
          severity: PtwValidationSeverity.error,
          templateId: rawTemplate['id'] as String?,
        ),
      );
    }

    return PtwTemplateProposalValidation(
      catalogRevision: snapshot.revision,
      normalizedTemplate: normalizedTemplate,
      mergedTheme: mergedTheme,
      score: score,
      issues: _deduplicateIssues(issues),
    );
  }

  Future<Map<String, dynamic>> upsertTemplate({
    required Map<String, dynamic> rawTemplate,
    required String expectedCatalogRevision,
  }) async {
    final snapshot = await load();
    if (snapshot.revision != expectedCatalogRevision) {
      return {
        'protocolVersion': ptwTemplateGeneratorProtocolVersion,
        'applied': false,
        'idempotent': false,
        'catalogRevision': snapshot.revision,
        'issues': [
          const PtwCatalogIssue(
            code: 'stale_catalog_revision',
            message:
                'The catalog changed after context was read. Refresh context and validate again.',
            severity: PtwValidationSeverity.error,
          ).toJson(),
        ],
      };
    }

    final validation = validateTemplateAgainst(snapshot, rawTemplate);
    if (!validation.isValid) {
      return {
        ...validation.toJson(),
        'applied': false,
        'idempotent': false,
      };
    }

    final template = validation.normalizedTemplate!;
    final existing = snapshot.theme.templates
        .where((item) => item.id == template.id)
        .firstOrNull;
    if (existing != null &&
        _canonicalJson(existing.toJson()) ==
            _canonicalJson(template.toJson())) {
      return {
        ...validation.toJson(),
        'applied': false,
        'idempotent': true,
        'templateId': template.id,
        'templateVersion': template.templateVersion,
      };
    }

    final normalizedJson = _normalizedThemeJson(validation.mergedTheme!);
    await _writeAtomically(catalogFile, normalizedJson);
    return {
      ...validation.toJson(),
      'applied': true,
      'idempotent': false,
      'templateId': template.id,
      'templateVersion': template.templateVersion,
      'catalogRevision': _revision(normalizedJson),
    };
  }

  Future<Map<String, dynamic>> exportRuntimeTheme() async {
    final snapshot = await load();
    final validations = PtwTemplateValidator.validateTheme(snapshot.theme);
    final issues = [
      for (final validation in validations)
        for (final issue in validation.issues)
          PtwCatalogIssue(
            code: issue.code,
            message: issue.message,
            severity: issue.severity,
            templateId: validation.template.id,
          ),
    ];
    final errors = issues
        .where((issue) => issue.severity == PtwValidationSeverity.error)
        .toList();
    if (errors.isNotEmpty) {
      return {
        'protocolVersion': ptwTemplateGeneratorProtocolVersion,
        'valid': false,
        'catalogRevision': snapshot.revision,
        'issues': _deduplicateIssues(issues)
            .map((issue) => issue.toJson())
            .toList(),
      };
    }
    return {
      'protocolVersion': ptwTemplateGeneratorProtocolVersion,
      'valid': true,
      'catalogRevision': snapshot.revision,
      'schemaVersion': snapshot.theme.schemaVersion,
      'designSystemVersion': snapshot.theme.designSystemVersion,
      'theme': snapshot.theme.toJson(),
      'issues': _deduplicateIssues(issues)
          .where((issue) => issue.severity != PtwValidationSeverity.note)
          .map((issue) => issue.toJson())
          .toList(),
    };
  }

  List<PtwCatalogIssue> _validateAuthoringSurface(
    ShareThemeConfig theme,
    Map<String, dynamic> rawTemplate,
  ) {
    final issues = <PtwCatalogIssue>[];
    final templateId = rawTemplate['id'] as String?;
    void error(String code, String message) => issues.add(
      PtwCatalogIssue(
        code: code,
        message: message,
        severity: PtwValidationSeverity.error,
        templateId: templateId,
      ),
    );

    final unknownTemplateKeys = rawTemplate.keys.toSet().difference(
      allowedTemplateKeys,
    );
    if (unknownTemplateKeys.isNotEmpty) {
      error(
        'template_keys',
        'Unsupported template fields: ${_sorted(unknownTemplateKeys).join(', ')}.',
      );
    }
    if (templateId == null ||
        !RegExp(r'^[a-z][a-z0-9_]{2,63}$').hasMatch(templateId)) {
      error(
        'template_id',
        'Template id must match ^[a-z][a-z0-9_]{2,63}\$.',
      );
    }
    if (rawTemplate['status'] != ShareTemplateStatus.production.name) {
      error('template_status', 'Installed templates must be production.');
    }
    if (rawTemplate['designSystemVersion'] != theme.designSystemVersion) {
      error(
        'design_system_version',
        'Template designSystemVersion must be ${theme.designSystemVersion}.',
      );
    }

    final layerIds = theme.layers.map((layer) => layer.id).toSet();
    final rawOverrides = rawTemplate['layerOverrides'];
    if (rawOverrides is! Map) {
      error('layer_overrides', 'layerOverrides must be an object.');
      return issues;
    }
    for (final entry in rawOverrides.entries) {
      final layerId = entry.key;
      if (layerId is! String || !layerIds.contains(layerId)) {
        error('layer_id', 'Unknown layer override: $layerId.');
        continue;
      }
      final value = entry.value;
      if (value is! Map) {
        error('layer_override', 'Override for $layerId must be an object.');
        continue;
      }
      final override = Map<String, dynamic>.from(value);
      final unknownKeys = override.keys.toSet().difference(
        allowedLayerOverrideKeys,
      );
      if (unknownKeys.isNotEmpty) {
        error(
          'layer_override_keys',
          '$layerId has unsupported override fields: ${_sorted(unknownKeys).join(', ')}.',
        );
      }
      if (override.containsKey('visible') && override['visible'] is! bool) {
        error('layer_visibility', '$layerId.visible must be a boolean.');
      }
      final emphasis = override['emphasis'];
      if (emphasis != null &&
          (emphasis is! String ||
              !ShareLayerEmphasis.values.any(
                (candidate) => candidate.name == emphasis,
              ))) {
        error('layer_emphasis', '$layerId.emphasis is invalid.');
      }
      final styleValue = override['style'];
      if (styleValue != null) {
        if (styleValue is! Map) {
          error('layer_style', '$layerId.style must be an object.');
        } else {
          final style = Map<String, dynamic>.from(styleValue);
          final unknownStyleKeys = style.keys.toSet().difference(
            allowedLayerStyleKeys,
          );
          if (unknownStyleKeys.isNotEmpty) {
            error(
              'layer_style_keys',
              '$layerId.style has unsupported fields: ${_sorted(unknownStyleKeys).join(', ')}.',
            );
          }
          for (final key in const ['fontSize', 'minFontSize']) {
            final value = style[key];
            if (value != null && (value is! num || value <= 0)) {
              error('layer_style_value', '$layerId.style.$key must be positive.');
            }
          }
          final maxLines = style['maxLines'];
          if (maxLines != null &&
              (maxLines is! int || maxLines < 1 || maxLines > 12)) {
            error(
              'layer_style_value',
              '$layerId.style.maxLines must be an integer from 1 to 12.',
            );
          }
        }
      }
    }
    return issues;
  }

  List<PtwCatalogIssue> _validateVersion(
    ShareThemeConfig theme,
    ShareTemplateConfig template,
  ) {
    final existing = theme.templates
        .where((item) => item.id == template.id)
        .firstOrNull;
    final identical =
        existing != null &&
        _canonicalJson(existing.toJson()) ==
            _canonicalJson(template.toJson());
    final expected = existing == null ? 1 : existing.templateVersion + 1;
    if (!identical && template.templateVersion != expected) {
      return [
        PtwCatalogIssue(
          code: 'template_version',
          message:
              'Template ${template.id} must use templateVersion $expected.',
          severity: PtwValidationSeverity.error,
          templateId: template.id,
        ),
      ];
    }
    return const [];
  }

  static List<PtwCatalogIssue> _deduplicateIssues(
    List<PtwCatalogIssue> issues,
  ) {
    final seen = <String>{};
    return [
      for (final issue in issues)
        if (seen.add(
          '${issue.templateId}|${issue.severity.name}|${issue.code}|${issue.message}',
        ))
          issue,
    ];
  }

  static Map<String, dynamic> _deepCopy(Map<String, dynamic> source) =>
      jsonDecode(jsonEncode(source)) as Map<String, dynamic>;

  static String _normalizedThemeJson(ShareThemeConfig theme) =>
      '${ShareThemeBundle.toJsonString(theme)}\n';

  static String _canonicalJson(Object? value) => jsonEncode(value);

  static String _revision(String value) {
    var hash = 0xcbf29ce484222325;
    const prime = 0x100000001b3;
    const mask = 0xffffffffffffffff;
    for (final byte in utf8.encode(value)) {
      hash ^= byte;
      hash = (hash * prime) & mask;
    }
    return 'fnv1a64:${hash.toRadixString(16).padLeft(16, '0')}';
  }

  static List<String> _sorted(Iterable<String> values) =>
      values.toList()..sort();

  static Future<void> _writeAtomically(File target, String content) async {
    await target.parent.create(recursive: true);
    final temporary = File('${target.path}.${pid}.tmp');
    try {
      await temporary.writeAsString(content, flush: true);
      await temporary.rename(target.path);
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
  }
}

extension<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
