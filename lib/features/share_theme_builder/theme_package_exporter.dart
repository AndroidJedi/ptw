import 'dart:convert';

import 'package:archive/archive.dart';
import 'package:flutter/services.dart';

import '../../generated_share_editor/generated_share_editor.dart';

final class GeneratedSharePackage {
  const GeneratedSharePackage({
    required this.zipBytes,
    required this.portableJson,
    required this.runtimeJson,
  });

  final Uint8List zipBytes;
  final String portableJson;
  final String runtimeJson;
}

final class ShareThemePackageExporter {
  ShareThemePackageExporter({AssetBundle? bundle})
    : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;

  static const _runtimeSources = <String>[
    'generated_share_editor.dart',
    'src/share_controller.dart',
    'src/share_editor.dart',
    'src/share_png_exporter.dart',
    'src/share_renderer.dart',
    'src/share_theme.dart',
    'src/share_value.dart',
  ];

  Future<GeneratedSharePackage> generate(ShareThemeConfig theme) async {
    theme.validate();
    final archive = Archive();
    final runtimeJson = _deepCopy(theme.toJson());
    final portableJson = _deepCopy(theme.toJson());
    final runtimeAssets =
        (runtimeJson['assets'] as List<dynamic>).cast<Map<String, dynamic>>();
    final portableAssets =
        (portableJson['assets'] as List<dynamic>).cast<Map<String, dynamic>>();

    for (var index = 0; index < theme.assets.length; index++) {
      final asset = theme.assets[index];
      final bytes = await _assetBytes(asset);
      final extension = _extension(asset.mimeType);
      final fileName = '${_safe(asset.id)}_${_hash(bytes)}.$extension';
      final path = 'assets/$fileName';
      runtimeAssets[index]
        ..remove('data')
        ..['path'] = 'lib/generated_share_editor/$path';
      portableAssets[index]
        ..remove('path')
        ..['data'] = base64Encode(bytes);
      _addBytes(archive, 'generated_share_editor/$path', bytes);
    }

    for (final path in _runtimeSources) {
      final sourcePath = 'lib/generated_share_editor/$path';
      final source = await _bundle.loadString(sourcePath);
      _addString(archive, 'generated_share_editor/$path', source);
    }

    final runtime = const JsonEncoder.withIndent('  ').convert(runtimeJson);
    final portable = const JsonEncoder.withIndent('  ').convert(portableJson);
    _addString(
      archive,
      'generated_share_editor/config/share_theme.json',
      runtime,
    );
    _addString(archive, 'generated_share_editor/source_theme.json', portable);
    _addString(
      archive,
      'generated_share_editor/pubspec_snippet.yaml',
      _pubspecSnippet(runtimeAssets),
    );
    _addString(archive, 'generated_share_editor/README.md', _readme(theme));
    final sortedArchive = Archive();
    final sortedFiles = [...archive.files]
      ..sort((left, right) => left.name.compareTo(right.name));
    for (final file in sortedFiles) {
      sortedArchive.addFile(file);
    }
    return GeneratedSharePackage(
      zipBytes: ZipEncoder().encodeBytes(sortedArchive),
      portableJson: portable,
      runtimeJson: runtime,
    );
  }

  Future<String> portableJson(ShareThemeConfig theme) async {
    theme.validate();
    final portable = _deepCopy(theme.toJson());
    final assets =
        (portable['assets'] as List<dynamic>).cast<Map<String, dynamic>>();
    for (var index = 0; index < theme.assets.length; index++) {
      final bytes = await _assetBytes(theme.assets[index]);
      assets[index]
        ..remove('path')
        ..['data'] = base64Encode(bytes);
    }
    return const JsonEncoder.withIndent('  ').convert(portable);
  }

  Future<Uint8List> _assetBytes(ShareAssetConfig asset) async {
    final embedded = asset.embeddedBytes;
    if (embedded != null) return embedded;
    final path = asset.path;
    if (path == null) {
      throw FormatException('Asset ${asset.id} has no bytes or path');
    }
    final data = await _bundle.load(path);
    return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
  }

  void _addString(Archive archive, String path, String content) =>
      _addBytes(archive, path, utf8.encode(content));

  void _addBytes(Archive archive, String path, List<int> bytes) {
    final file =
        ArchiveFile.bytes(path, bytes)
          ..creationTime = 0
          ..lastModTime = 0;
    archive.addFile(file);
  }

  Map<String, dynamic> _deepCopy(Map<String, dynamic> source) =>
      jsonDecode(jsonEncode(source)) as Map<String, dynamic>;

  String _extension(String mimeType) => switch (mimeType.toLowerCase()) {
    'image/jpeg' => 'jpg',
    'image/webp' => 'webp',
    'font/ttf' || 'application/x-font-ttf' => 'ttf',
    'font/otf' || 'application/x-font-opentype' => 'otf',
    _ => 'png',
  };

  String _safe(String value) {
    final safe = value
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9_]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
    return safe.isEmpty ? 'asset' : safe;
  }

  String _hash(List<int> bytes) {
    var hash = 0x811c9dc5;
    for (final byte in bytes) {
      hash ^= byte;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }

  String _readme(ShareThemeConfig theme) => '''
# ${theme.name} generated share editor

Copy this entire `generated_share_editor` directory into your Flutter app's
`lib/` directory. Merge `pubspec_snippet.yaml` into the host `pubspec.yaml`,
then run `flutter pub get`.

```dart
final theme = await ShareThemeBundle.loadAsset();
final controller = ShareEditorController(
  theme: theme,
  content: content,
  initialValue: savedValue,
  mode: ShareEditorMode.runtime,
  entitlements: (key) => currentUserEntitlements.contains(key),
);

GeneratedShareEditor(
  theme: theme,
  content: content,
  controller: controller,
  onChanged: (value) => save(value.toJson()),
  onLockedFeatureTap: showUpgrade,
);
```

The host app owns navigation, persistence, image picking, subscriptions,
copy-link behavior, and native sharing. Templates own structure and runtime
permissions; looks own visual treatment. Persist `ShareEditorValue.templateId`
with the rest of the value. Use `GeneratedShareRenderer` for a read-only
preview and `SharePngExporter` for the exact PNG. Safe-zone guides are
authoring-only and are omitted unless `showAuthoringGuides` is explicitly set.
''';

  String _pubspecSnippet(List<Map<String, dynamic>> runtimeAssets) {
    final fonts = runtimeAssets.where((asset) => asset['kind'] == 'font');
    final buffer = StringBuffer('''
flutter:
  assets:
    - lib/generated_share_editor/config/
    - lib/generated_share_editor/assets/
''');
    if (fonts.isNotEmpty) {
      buffer.writeln('  fonts:');
      final families = <String, List<Map<String, dynamic>>>{};
      for (final font in fonts) {
        families.putIfAbsent(font['fontFamily'] as String, () => []).add(font);
      }
      for (final entry in families.entries) {
        buffer.writeln("    - family: '${_yaml(entry.key)}'");
        buffer.writeln('      fonts:');
        for (final font in entry.value) {
          buffer.writeln("        - asset: ${font['path']}");
          if (font['fontWeight'] != null) {
            buffer.writeln('          weight: ${font['fontWeight']}');
          }
          if (font['italic'] == true) buffer.writeln('          style: italic');
        }
      }
    }
    return buffer.toString();
  }

  String _yaml(String value) => value.replaceAll("'", "''");
}
