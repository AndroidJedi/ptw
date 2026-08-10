import 'dart:io';

const ptwCatalogRelativePath = 'tool/ptw_template_mcp/catalog/share_theme.json';
const ptwRuntimeThemeRelativePath =
    'lib/generated_share_editor/config/share_theme.json';
const ptwMcpServerRelativePath = 'tool/ptw_template_mcp/server.dart';

Directory discoverPtwProjectRoot({Directory? start}) {
  final starts = <Directory>[
    start ?? Directory.current,
    if (Platform.script.scheme == 'file') File.fromUri(Platform.script).parent,
  ];
  final visited = <String>{};
  for (final candidate in starts) {
    var directory = candidate.absolute;
    while (visited.add(directory.path)) {
      final hasPackage = File('${directory.path}/pubspec.yaml').existsSync();
      final hasTheme =
          File('${directory.path}/$ptwRuntimeThemeRelativePath').existsSync();
      if (hasPackage && hasTheme) return directory;
      final parent = directory.parent;
      if (parent.path == directory.path) break;
      directory = parent;
    }
  }
  throw StateError(
    'Could not find the PTW project root from ${Directory.current.path}.',
  );
}

String? readOption(List<String> arguments, String option) {
  final index = arguments.indexOf(option);
  if (index == -1) return null;
  if (index + 1 >= arguments.length || arguments[index + 1].startsWith('--')) {
    throw FormatException('$option requires a value.');
  }
  return arguments[index + 1];
}

File resolveProjectFile(Directory root, String path) =>
    File(path).isAbsolute ? File(path) : File('${root.path}/$path');
