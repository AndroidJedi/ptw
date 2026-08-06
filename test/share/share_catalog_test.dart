import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('catalog defines every template and platform guide', () async {
    final raw = await rootBundle.loadString('assets/mock/share_content.json');
    final catalog = ShareCatalog.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );

    expect(catalog.templates.keys, containsAll(ShareTemplateType.values));
    expect(catalog.guides.keys, containsAll(SharePlatform.values));
    expect(
      catalog.scenarios.map((item) => item.template),
      containsAll(ShareTemplateType.values),
    );
    for (final type in ShareTemplateType.values) {
      expect(catalog.template(type).variations, hasLength(3));
      final scenario = catalog.scenarios.singleWhere(
        (item) => item.template == type,
      );
      expect(ShareCardData.fromJson(scenario.toJson()).template, type);
    }
    expect(catalog.guide(SharePlatform.instagramStories).steps, hasLength(4));
  });

  test('catalog rejects a malformed type-specific fallback', () {
    final malformed = <String, dynamic>{
      'templates': [
        {
          'type': 'criticism',
          'fallback': {'authorResponse': 'Let us see.'},
          'variations': [
            {
              'hook': 'Hook',
              'caption': 'Caption',
              'cta': 'CTA',
              'gradientVariant': 0,
            },
          ],
        },
      ],
      'guides': <dynamic>[],
    };

    expect(
      () => ShareCatalog.fromJson(malformed),
      throwsA(isA<FormatException>()),
    );
  });
}
