import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mcp_dart/mcp_dart.dart';

import '../../tool/ptw_template_mcp/sync.dart' as sync;

void main() {
  late Directory projectRoot;
  late Directory temporaryDirectory;
  late File catalogFile;

  setUp(() async {
    projectRoot = Directory.current.absolute;
    temporaryDirectory = await Directory.systemTemp.createTemp(
      'ptw-template-mcp-test-',
    );
    catalogFile = File('${temporaryDirectory.path}/share_theme.json');
    await File(
      '${projectRoot.path}/tool/ptw_template_mcp/catalog/share_theme.json',
    ).copy(catalogFile.path);
  });

  tearDown(() async {
    if (await temporaryDirectory.exists()) {
      await temporaryDirectory.delete(recursive: true);
    }
  });

  test(
    'real STDIO server supports discovery, authoring, export, and shutdown',
    () async {
      final client = _client();
      try {
        await client.connect(_transport(projectRoot, catalogFile));

        final tools = await client.listTools();
        expect(
          tools.tools.map((tool) => tool.name).toSet(),
          containsAll({
            'get_template_context',
            'validate_template',
            'upsert_template',
            'export_runtime_theme',
          }),
        );
        final resources = await client.listResources();
        expect(
          resources.resources.map((resource) => resource.uri),
          containsAll({
            'ptw://template-generator/contract',
            'ptw://template-generator/catalog',
          }),
        );
        final prompts = await client.listPrompts();
        expect(
          prompts.prompts.map((prompt) => prompt.name),
          contains('author_ptw_template'),
        );

        final context = _object(
          await client.callTool(
            const CallToolRequest(
              name: 'get_template_context',
              arguments: {'family': 'heroPhoto', 'journeyState': 'beginning'},
            ),
          ),
        );
        expect(context['schemaVersion'], 3);
        final oldRevision = context['catalogRevision']! as String;
        final example = Map<String, dynamic>.from(
          (context['templates']! as List<dynamic>).first as Map,
        );
        final proposal =
            Map<String, dynamic>.from(example)
              ..['id'] = 'stdio_authored_template'
              ..['label'] = 'STDIO Authored Template'
              ..['templateVersion'] = 1;

        final validation = _object(
          await client.callTool(
            CallToolRequest(
              name: 'validate_template',
              arguments: {'template': proposal},
            ),
          ),
        );
        expect(validation['valid'], isTrue, reason: jsonEncode(validation));

        final upsert = _object(
          await client.callTool(
            CallToolRequest(
              name: 'upsert_template',
              arguments: {
                'template': proposal,
                'expectedCatalogRevision': oldRevision,
              },
            ),
          ),
        );
        expect(upsert['applied'], isTrue, reason: jsonEncode(upsert));

        final stale = _object(
          await client.callTool(
            CallToolRequest(
              name: 'upsert_template',
              arguments: {
                'template': proposal,
                'expectedCatalogRevision': oldRevision,
              },
            ),
          ),
        );
        expect(stale['applied'], isFalse);
        expect(
          (stale['issues']! as List<dynamic>).cast<Map<String, dynamic>>().map(
            (issue) => issue['code'],
          ),
          contains('stale_catalog_revision'),
        );

        final exported = _object(
          await client.callTool(
            const CallToolRequest(name: 'export_runtime_theme', arguments: {}),
          ),
        );
        expect(exported['valid'], isTrue);
        expect(exported['catalogRevision'], upsert['catalogRevision']);
        final theme = exported['theme']! as Map<String, dynamic>;
        expect(
          (theme['templates']! as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map((template) => template['id']),
          contains('stdio_authored_template'),
        );
      } finally {
        await client.close();
      }
    },
  );

  test(
    'sync is idempotent and check detects stale output without writing',
    () async {
      final output = File('${temporaryDirectory.path}/runtime_theme.json');

      final first = await sync.synchronizePtwRuntimeTheme(
        projectRoot: projectRoot,
        catalogPath: catalogFile.path,
        outputPath: output.path,
        dartExecutable: 'dart',
      );
      final synchronized = await output.readAsString();
      final second = await sync.synchronizePtwRuntimeTheme(
        projectRoot: projectRoot,
        catalogPath: catalogFile.path,
        outputPath: output.path,
        dartExecutable: 'dart',
      );

      expect(first.changed, isTrue);
      expect(second.changed, isFalse);
      expect(second.catalogRevision, first.catalogRevision);

      await output.writeAsString('$synchronized ');
      final staleBytes = await output.readAsString();
      await expectLater(
        sync.synchronizePtwRuntimeTheme(
          check: true,
          projectRoot: projectRoot,
          catalogPath: catalogFile.path,
          outputPath: output.path,
          dartExecutable: 'dart',
        ),
        throwsA(isA<sync.PtwRuntimeThemeStale>()),
      );
      expect(await output.readAsString(), staleBytes);
    },
  );

  test('invalid catalogs leave catalog and app output unchanged', () async {
    final output = File('${temporaryDirectory.path}/runtime_theme.json');
    await output.writeAsString('known-good-output');
    final decoded =
        jsonDecode(await catalogFile.readAsString()) as Map<String, dynamic>;
    final templates =
        (decoded['templates']! as List<dynamic>).cast<Map<String, dynamic>>();
    templates.first['safeZones'] = <dynamic>[];
    await catalogFile.writeAsString(jsonEncode(decoded));
    final invalidCatalog = await catalogFile.readAsString();

    await expectLater(
      sync.synchronizePtwRuntimeTheme(
        projectRoot: projectRoot,
        catalogPath: catalogFile.path,
        outputPath: output.path,
        dartExecutable: 'dart',
      ),
      throwsA(isA<StateError>()),
    );

    expect(await catalogFile.readAsString(), invalidCatalog);
    expect(await output.readAsString(), 'known-good-output');
  });
}

McpClient _client() => McpClient(
  const Implementation(name: 'ptw-template-mcp-test', version: '1.0.0'),
  options: const McpClientOptions(
    protocol: McpProtocol.stable,
    capabilities: ClientCapabilities(),
  ),
);

StdioClientTransport _transport(Directory root, File catalog) =>
    StdioClientTransport(
      StdioServerParameters(
        command: 'dart',
        args: [
          'run',
          'tool/ptw_template_mcp/server.dart',
          '--stdio',
          '--catalog',
          catalog.path,
        ],
        workingDirectory: root.path,
        stderrMode: ProcessStartMode.normal,
        restartOnUnexpectedExit: false,
      ),
    );

Map<String, dynamic> _object(CallToolResult result) {
  expect(result.isError, isFalse, reason: result.toJson().toString());
  final structured = result.structuredContent;
  if (structured != null) return structured;
  final text = result.content.whereType<TextContent>().first.text;
  return jsonDecode(text) as Map<String, dynamic>;
}
