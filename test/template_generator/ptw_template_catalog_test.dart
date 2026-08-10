import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/template_generator/ptw_template_catalog.dart';

void main() {
  late Directory temporaryDirectory;
  late File catalogFile;
  late PtwTemplateCatalog catalog;

  setUp(() async {
    temporaryDirectory = await Directory.systemTemp.createTemp(
      'ptw-template-catalog-test-',
    );
    catalogFile = File('${temporaryDirectory.path}/share_theme.json');
    await File(
      'tool/ptw_template_mcp/catalog/share_theme.json',
    ).copy(catalogFile.path);
    catalog = PtwTemplateCatalog(catalogFile);
  });

  tearDown(() async {
    if (await temporaryDirectory.exists()) {
      await temporaryDirectory.delete(recursive: true);
    }
  });

  test('plain-Dart catalog parsing and revisions are deterministic', () async {
    final first = await catalog.load();
    await catalogFile.writeAsString(first.normalizedJson);
    final second = await catalog.load();

    expect(second.revision, first.revision);
    expect(second.theme.schemaVersion, 3);
    expect(second.theme.templates, isNotEmpty);

    final context = await catalog.context(
      family: 'comparison',
      journeyState: 'milestone',
    );
    final templates = context['templates']! as List<dynamic>;
    expect(templates, isNotEmpty);
    expect(
      templates.cast<Map<String, dynamic>>(),
      everyElement(containsPair('family', 'comparison')),
    );
    expect(context['catalogRevision'], first.revision);
  });

  test('validation normalizes a valid new template without writing', () async {
    final before = await catalogFile.readAsString();
    final proposal = await _newTemplate(catalog, id: 'test_hero_template');

    final validation = await catalog.validateTemplate(proposal);

    expect(validation.isValid, isTrue, reason: _issueSummary(validation));
    expect(validation.normalizedTemplate!.id, 'test_hero_template');
    expect(validation.normalizedTemplate!.templateVersion, 1);
    expect(validation.score, greaterThan(0));
    expect(await catalogFile.readAsString(), before);
  });

  test('unsafe layer style overrides are rejected without writing', () async {
    final before = await catalogFile.readAsString();
    final proposal = await _newTemplate(catalog, id: 'unsafe_style_test');
    final overrides = proposal['layerOverrides']! as Map<String, dynamic>;
    final headline = Map<String, dynamic>.from(overrides['headline']! as Map);
    headline['style'] = {'fontFamily': 'ExternalFont'};
    overrides['headline'] = headline;

    final validation = await catalog.validateTemplate(proposal);

    expect(validation.isValid, isFalse);
    expect(
      validation.issues.map((issue) => issue.code),
      contains('layer_style_keys'),
    );
    expect(await catalogFile.readAsString(), before);
  });

  test(
    'new and replacement versions plus identical retries are enforced',
    () async {
      final initial = await catalog.load();
      final wrongVersion = await _newTemplate(
        catalog,
        id: 'versioned_template',
        version: 2,
      );
      final rejected = await catalog.upsertTemplate(
        rawTemplate: wrongVersion,
        expectedCatalogRevision: initial.revision,
      );
      expect(rejected['applied'], isFalse);
      expect(_issueCodes(rejected), contains('template_version'));
      expect((await catalog.load()).revision, initial.revision);

      final versionOne = await _newTemplate(catalog, id: 'versioned_template');
      final inserted = await catalog.upsertTemplate(
        rawTemplate: versionOne,
        expectedCatalogRevision: initial.revision,
      );
      expect(inserted['applied'], isTrue, reason: jsonEncode(inserted));
      final insertedRevision = inserted['catalogRevision']! as String;

      final retry = await catalog.upsertTemplate(
        rawTemplate: versionOne,
        expectedCatalogRevision: insertedRevision,
      );
      expect(retry['applied'], isFalse);
      expect(retry['idempotent'], isTrue);
      expect(retry['catalogRevision'], insertedRevision);

      final wrongReplacement = Map<String, dynamic>.from(versionOne)
        ..['label'] = 'Changed label';
      final replacementRejected = await catalog.upsertTemplate(
        rawTemplate: wrongReplacement,
        expectedCatalogRevision: insertedRevision,
      );
      expect(replacementRejected['applied'], isFalse);
      expect(_issueCodes(replacementRejected), contains('template_version'));

      final replacement = Map<String, dynamic>.from(wrongReplacement)
        ..['templateVersion'] = 2;
      final replaced = await catalog.upsertTemplate(
        rawTemplate: replacement,
        expectedCatalogRevision: insertedRevision,
      );
      expect(replaced['applied'], isTrue, reason: jsonEncode(replaced));
    },
  );

  test('stale revisions never modify the catalog', () async {
    final before = await catalogFile.readAsString();
    final proposal = await _newTemplate(catalog, id: 'stale_write_test');

    final result = await catalog.upsertTemplate(
      rawTemplate: proposal,
      expectedCatalogRevision: 'fnv1a64:0000000000000000',
    );

    expect(result['applied'], isFalse);
    expect(_issueCodes(result), contains('stale_catalog_revision'));
    expect(await catalogFile.readAsString(), before);
  });
}

Future<Map<String, dynamic>> _newTemplate(
  PtwTemplateCatalog catalog, {
  required String id,
  int version = 1,
}) async {
  final snapshot = await catalog.load();
  final source = snapshot.theme.templates.first.toJson();
  return jsonDecode(
        jsonEncode({
          ...source,
          'id': id,
          'label': 'Test template $id',
          'templateVersion': version,
        }),
      )
      as Map<String, dynamic>;
}

Iterable<String> _issueCodes(Map<String, dynamic> result) =>
    (result['issues']! as List<dynamic>).cast<Map<String, dynamic>>().map(
      (issue) => issue['code']! as String,
    );

String _issueSummary(PtwTemplateProposalValidation validation) => validation
    .issues
    .map((issue) => '${issue.code}: ${issue.message}')
    .join('\n');
