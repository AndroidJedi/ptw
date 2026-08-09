import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/ptw_template_validator.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'bundled experimental templates are structurally export ready',
    () async {
      final theme = await ShareThemeBundle.loadAsset();
      final results = PtwTemplateValidator.validateTheme(theme);

      expect(results.map((result) => result.template.id), [
        'hero_photo',
        'progress',
        'comparison',
      ]);
      expect(results.every((result) => result.isReady), isTrue);
      expect(results.every((result) => result.score >= 90), isTrue);
    },
  );

  test('validator reports missing required roles and safe zones', () async {
    final source = (await ShareThemeBundle.loadAsset()).toJson();
    final templates =
        (source['templates'] as List<dynamic>).cast<Map<String, dynamic>>();
    final hero = templates.first;
    hero['requiredContentRoles'] = ['heroMedia', 'headline', 'brand', 'proof'];
    hero['safeZones'] = <Object?>[];
    final theme = ShareThemeConfig.fromJson(source);

    final result = PtwTemplateValidator.validate(theme, theme.templates.first);

    expect(result.isReady, isFalse);
    expect(
      result.issues.map((issue) => issue.code),
      containsAll(['required_proof', 'safe_zones']),
    );
  });
}
