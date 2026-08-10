import 'dart:convert';
import 'dart:io';

import 'package:mcp_dart/mcp_dart.dart';
import 'package:ptw/features/share_theme_builder/ptw_template_validator.dart';
import 'package:ptw/generated_share_editor/src/share_theme.dart';
import 'package:ptw/template_generator/ptw_template_catalog.dart';

import 'paths.dart';

const _requiredTools = {
  'get_template_context',
  'validate_template',
  'upsert_template',
  'export_runtime_theme',
};

Future<void> main(List<String> arguments) async {
  if (arguments.contains('--help')) {
    stdout.writeln(
      'Usage: dart run tool/ptw_template_mcp/sync.dart [--check] '
      '[--catalog <path>] [--output <path>]',
    );
    return;
  }

  try {
    final result = await synchronizePtwRuntimeTheme(
      check: arguments.contains('--check'),
      catalogPath: readOption(arguments, '--catalog'),
      outputPath: readOption(arguments, '--output'),
    );
    stdout.writeln(result.message);
  } on PtwRuntimeThemeStale catch (error) {
    stderr.writeln(error.message);
    exitCode = 2;
  } on Object catch (error, stackTrace) {
    stderr
      ..writeln('PTW template synchronization failed: $error')
      ..writeln(stackTrace);
    exitCode = 1;
  }
}

final class PtwThemeSyncResult {
  const PtwThemeSyncResult({
    required this.changed,
    required this.catalogRevision,
    required this.outputFile,
    required this.message,
  });

  final bool changed;
  final String catalogRevision;
  final File outputFile;
  final String message;
}

final class PtwRuntimeThemeStale implements Exception {
  const PtwRuntimeThemeStale(this.message);

  final String message;

  @override
  String toString() => message;
}

Future<PtwThemeSyncResult> synchronizePtwRuntimeTheme({
  bool check = false,
  String? catalogPath,
  String? outputPath,
  String? dartExecutable,
  Directory? projectRoot,
}) async {
  final root = projectRoot ?? discoverPtwProjectRoot();
  final catalog = resolveProjectFile(
    root,
    catalogPath ?? ptwCatalogRelativePath,
  );
  final output = resolveProjectFile(
    root,
    outputPath ?? ptwRuntimeThemeRelativePath,
  );
  if (!await catalog.exists()) {
    throw StateError('PTW template catalog not found: ${catalog.path}');
  }

  final transport = StdioClientTransport(
    StdioServerParameters(
      command: dartExecutable ?? Platform.resolvedExecutable,
      args: [
        'run',
        ptwMcpServerRelativePath,
        '--stdio',
        '--catalog',
        catalog.path,
      ],
      workingDirectory: root.path,
      stderrMode: ProcessStartMode.inheritStdio,
      restartOnUnexpectedExit: false,
    ),
  );
  final client = McpClient(
    const Implementation(
      name: 'ptw-template-sync',
      version: ptwTemplateGeneratorProtocolVersion,
    ),
    options: const McpClientOptions(
      protocol: McpProtocol.stable,
      capabilities: ClientCapabilities(),
    ),
  );

  Map<String, dynamic> exported;
  try {
    await client.connect(transport);
    final discovered = await client.listTools();
    final names = discovered.tools.map((tool) => tool.name).toSet();
    final missing = _requiredTools.difference(names);
    if (missing.isNotEmpty) {
      throw StateError(
        'PTW MCP server is missing required tools: '
        '${(missing.toList()..sort()).join(', ')}.',
      );
    }

    final result = await client.callTool(
      const CallToolRequest(name: 'export_runtime_theme', arguments: {}),
    );
    if (result.isError) {
      throw StateError('export_runtime_theme failed: ${_toolText(result)}');
    }
    exported = _toolObject(result);
  } finally {
    await client.close();
  }

  if (exported['valid'] != true) {
    throw StateError(
      'The MCP server refused to export an invalid catalog: '
      '${jsonEncode(exported['issues'])}',
    );
  }
  final revision = exported['catalogRevision'];
  if (revision is! String || revision.isEmpty) {
    throw const FormatException('MCP export omitted catalogRevision.');
  }
  final themeJson = _jsonObject(exported['theme'], 'theme');
  final theme = ShareThemeConfig.fromJson(themeJson);
  final localErrors = [
    for (final validation in PtwTemplateValidator.validateTheme(theme))
      for (final issue in validation.issues)
        if (issue.severity == PtwValidationSeverity.error)
          '${validation.template.id}:${issue.code}: ${issue.message}',
  ];
  if (localErrors.isNotEmpty) {
    throw StateError(
      'Local validation rejected MCP export:\n${localErrors.join('\n')}',
    );
  }

  final normalized = '${ShareThemeBundle.toJsonString(theme)}\n';
  final existing = await output.exists() ? await output.readAsString() : null;
  final changed = existing != normalized;
  if (check && changed) {
    throw PtwRuntimeThemeStale(
      'PTW runtime theme is stale: ${output.path}. '
      'Run dart run tool/ptw_template_mcp/sync.dart.',
    );
  }
  if (changed) await _writeAtomically(output, normalized);

  final action = changed ? 'Synchronized' : 'Verified';
  return PtwThemeSyncResult(
    changed: changed,
    catalogRevision: revision,
    outputFile: output,
    message: '$action PTW runtime theme $revision at ${output.path}.',
  );
}

Map<String, dynamic> _toolObject(CallToolResult result) {
  final structured = result.structuredContent;
  if (structured != null) return structured;
  final decoded = jsonDecode(_toolText(result));
  return _jsonObject(decoded, 'tool result');
}

String _toolText(CallToolResult result) {
  for (final content in result.content) {
    if (content is TextContent) return content.text;
  }
  return '<no text content>';
}

Map<String, dynamic> _jsonObject(Object? value, String field) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  throw FormatException('$field must be a JSON object.');
}

Future<void> _writeAtomically(File target, String content) async {
  await target.parent.create(recursive: true);
  final temporary = File('${target.path}.$pid.tmp');
  try {
    await temporary.writeAsString(content, flush: true);
    await temporary.rename(target.path);
  } finally {
    if (await temporary.exists()) await temporary.delete();
  }
}
