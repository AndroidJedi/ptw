import 'dart:convert';

import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/theme_package_exporter.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('generated ZIP is deterministic, rooted, and self-contained', () async {
    final theme = await ShareThemeBundle.loadAsset();
    final exporter = ShareThemePackageExporter();
    final first = await exporter.generate(theme);
    final second = await exporter.generate(theme);
    expect(second.zipBytes, orderedEquals(first.zipBytes));

    final archive = ZipDecoder().decodeBytes(first.zipBytes);
    final names = archive.files.map((file) => file.name).toList();
    expect(names, orderedEquals([...names]..sort()));
    expect(
      names,
      containsAll(const [
        'generated_share_editor/generated_share_editor.dart',
        'generated_share_editor/config/share_theme.json',
        'generated_share_editor/source_theme.json',
        'generated_share_editor/README.md',
        'generated_share_editor/pubspec_snippet.yaml',
      ]),
    );
    expect(
      names.where((name) => name.startsWith('generated_share_editor/assets/')),
      hasLength(theme.assets.length),
    );

    final runtime = jsonDecode(first.runtimeJson) as Map<String, dynamic>;
    final runtimeAssets =
        (runtime['assets'] as List<dynamic>).cast<Map<String, dynamic>>();
    expect(runtimeAssets.every((asset) => asset['data'] == null), isTrue);
    expect(
      runtimeAssets.every(
        (asset) => RegExp(
          r'^lib/generated_share_editor/assets/.+_[0-9a-f]{8}\.(?:png|jpg|webp|ttf|otf)$',
        ).hasMatch(asset['path'] as String),
      ),
      isTrue,
    );

    final portable = jsonDecode(first.portableJson) as Map<String, dynamic>;
    final portableAssets =
        (portable['assets'] as List<dynamic>).cast<Map<String, dynamic>>();
    expect(portableAssets.every((asset) => asset['path'] == null), isTrue);
    expect(portableAssets.every((asset) => asset['data'] is String), isTrue);
  });
}
