import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled PTW theme validates and round-trips', () async {
    final theme = await ShareThemeBundle.loadAsset();
    expect(theme.id, 'ptw_story_v1');
    expect(theme.looks, hasLength(6));
    expect(theme.canvas.outputWidth, 1080);
    final decoded = ShareThemeConfig.fromJson(
      jsonDecode(ShareThemeBundle.toJsonString(theme)) as Map<String, dynamic>,
    );
    expect(decoded.toJson(), theme.toJson());
  });

  test('unknown versions and duplicate IDs are rejected', () async {
    final source =
        jsonDecode(await rootBundle.loadString(ShareThemeBundle.defaultAsset))
            as Map<String, dynamic>;
    expect(
      () => ShareThemeConfig.fromJson({...source, 'schemaVersion': 99}),
      throwsFormatException,
    );
    final duplicate = jsonDecode(jsonEncode(source)) as Map<String, dynamic>;
    final layers = duplicate['layers'] as List<dynamic>;
    layers.add(Map<String, dynamic>.from(layers.first as Map));
    expect(() => ShareThemeConfig.fromJson(duplicate), throwsFormatException);
  });

  test(
    'bounds, gradients, bindings, assets, and access errors are actionable',
    () async {
      final raw = await rootBundle.loadString(ShareThemeBundle.defaultAsset);
      Map<String, dynamic> source() => jsonDecode(raw) as Map<String, dynamic>;

      final bounds = source();
      ((bounds['layers'] as List<dynamic>).first
          as Map<String, dynamic>)['transform'] = {
        'x': -1,
        'y': 0,
        'width': 360,
        'height': 640,
      };
      expect(
        () => ShareThemeConfig.fromJson(bounds),
        throwsA(
          isA<FormatException>().having(
            (error) => error.message,
            'message',
            contains('outside the canvas'),
          ),
        ),
      );

      final gradient = source();
      final backgrounds =
          (gradient['backgrounds'] as List<dynamic>)
              .cast<Map<String, dynamic>>();
      final hot = backgrounds.singleWhere(
        (item) => item['id'] == 'gradient_hot',
      );
      (hot['properties'] as Map<String, dynamic>)['stops'] = [0.8, 0.2];
      expect(
        () => ShareThemeConfig.fromJson(gradient),
        throwsA(
          isA<FormatException>().having(
            (error) => error.message,
            'message',
            contains('invalid stops'),
          ),
        ),
      );

      final binding = source();
      final layers =
          (binding['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
      layers.singleWhere((item) => item['id'] == 'headline')['binding'] = 'bad';
      expect(() => ShareThemeConfig.fromJson(binding), throwsFormatException);

      final asset = source();
      final assetLayers =
          (asset['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
      (assetLayers.singleWhere((item) => item['id'] == 'avatar')['style']
              as Map<String, dynamic>)['fallbackAssetId'] =
          'missing';
      expect(() => ShareThemeConfig.fromJson(asset), throwsFormatException);

      final access = source();
      final toolbar =
          (access['toolbar'] as List<dynamic>).cast<Map<String, dynamic>>();
      toolbar.first['access'] = {'mode': 'premiumVisible'};
      expect(() => ShareThemeConfig.fromJson(access), throwsFormatException);
    },
  );
}
