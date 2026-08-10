import 'dart:convert';
import 'dart:io';

import 'package:mcp_dart/mcp_dart.dart';
import 'package:ptw/template_generator/ptw_template_catalog.dart';

import 'paths.dart';

const _contractUri = 'ptw://template-generator/contract';
const _catalogUri = 'ptw://template-generator/catalog';

Future<void> main(List<String> arguments) async {
  try {
    if (arguments.contains('--help')) {
      stderr.writeln(
        'Usage: dart run tool/ptw_template_mcp/server.dart --stdio '
        '[--catalog <path>]',
      );
      return;
    }
    if (!arguments.contains('--stdio')) {
      throw const FormatException('Only the --stdio transport is supported.');
    }

    final root = discoverPtwProjectRoot();
    final catalogPath =
        readOption(arguments, '--catalog') ?? ptwCatalogRelativePath;
    final catalog = PtwTemplateCatalog(resolveProjectFile(root, catalogPath));
    await catalog.load();

    final server = createPtwTemplateMcpServer(catalog);
    stderr.writeln(
      'PTW template MCP server ready (${catalog.catalogFile.path}).',
    );
    await server.connect(StdioServerTransport());
  } on Object catch (error, stackTrace) {
    stderr
      ..writeln('PTW template MCP server failed: $error')
      ..writeln(stackTrace);
    exitCode = 64;
  }
}

McpServer createPtwTemplateMcpServer(PtwTemplateCatalog catalog) {
  final server = McpServer(
    const Implementation(
      name: 'ptw-template-generator',
      version: ptwTemplateGeneratorProtocolVersion,
    ),
    options: const McpServerOptions(
      protocol: McpProtocol.stable,
      instructions: ptwTemplateGeneratorInstructions,
      capabilities: ServerCapabilities(
        tools: ServerCapabilitiesTools(),
        resources: ServerCapabilitiesResources(),
        prompts: ServerCapabilitiesPrompts(),
      ),
    ),
  );

  server.registerTool(
    'get_template_context',
    title: 'Get PTW template context',
    description:
        'Returns schema, design-system, catalog, constraints, and relevant '
        'production template examples. Call this before authoring.',
    inputSchema: JsonSchema.object(
      properties: {
        'family': JsonSchema.string(
          description: 'Optional ShareTemplateFamily enum name.',
        ),
        'journeyState': JsonSchema.string(
          description: 'Optional ShareJourneyState enum name.',
        ),
      },
      additionalProperties: false,
    ),
    outputSchema: JsonSchema.object(additionalProperties: true),
    annotations: const ToolAnnotations(
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    ),
    callback:
        (arguments, extra) => _jsonResult(
          () => catalog.context(
            family: arguments['family'] as String?,
            journeyState: arguments['journeyState'] as String?,
          ),
        ),
  );

  server.registerTool(
    'validate_template',
    title: 'Validate PTW template',
    description:
        'Merges a proposed schema-v3 template in memory and returns its '
        'normalized form, readiness score, errors, and warnings without writing.',
    inputSchema: JsonSchema.object(
      properties: {'template': JsonSchema.object(additionalProperties: true)},
      required: ['template'],
      additionalProperties: false,
    ),
    outputSchema: JsonSchema.object(additionalProperties: true),
    annotations: const ToolAnnotations(
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    ),
    callback:
        (arguments, extra) => _jsonResult(
          () async => catalog
              .validateTemplate(_jsonObject(arguments['template'], 'template'))
              .then((validation) => validation.toJson()),
        ),
  );

  server.registerTool(
    'upsert_template',
    title: 'Install PTW template',
    description:
        'Atomically adds or replaces a validated production template when the '
        'catalog revision and template version are current.',
    inputSchema: JsonSchema.object(
      properties: {
        'template': JsonSchema.object(additionalProperties: true),
        'expectedCatalogRevision': JsonSchema.string(minLength: 1),
      },
      required: ['template', 'expectedCatalogRevision'],
      additionalProperties: false,
    ),
    outputSchema: JsonSchema.object(additionalProperties: true),
    annotations: const ToolAnnotations(
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    ),
    callback:
        (arguments, extra) => _jsonResult(
          () => catalog.upsertTemplate(
            rawTemplate: _jsonObject(arguments['template'], 'template'),
            expectedCatalogRevision:
                arguments['expectedCatalogRevision'] as String,
          ),
        ),
  );

  server.registerTool(
    'export_runtime_theme',
    title: 'Export PTW runtime theme',
    description:
        'Returns the complete normalized, validated catalog for deterministic '
        'synchronization into the Flutter application.',
    inputSchema: JsonSchema.object(
      properties: const {},
      additionalProperties: false,
    ),
    outputSchema: JsonSchema.object(additionalProperties: true),
    annotations: const ToolAnnotations(
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    ),
    callback: (arguments, extra) => _jsonResult(catalog.exportRuntimeTheme),
  );

  server.registerResource(
    'PTW template generator contract',
    _contractUri,
    (
      description: 'Authoring rules and workflow for schema-v3 PTW templates.',
      mimeType: 'text/markdown',
    ),
    (uri, extra) async => ReadResourceResult(
      contents: [
        TextResourceContents(
          uri: uri.toString(),
          mimeType: 'text/markdown',
          text: ptwTemplateGeneratorContract,
        ),
      ],
    ),
  );

  server.registerResource(
    'PTW template catalog',
    _catalogUri,
    (
      description: 'The current normalized template catalog and revision.',
      mimeType: 'application/json',
    ),
    (uri, extra) async => ReadResourceResult(
      contents: [
        TextResourceContents(
          uri: uri.toString(),
          mimeType: 'application/json',
          text: const JsonEncoder.withIndent(
            '  ',
          ).convert(await catalog.exportRuntimeTheme()),
        ),
      ],
    ),
  );

  server.registerPrompt(
    'author_ptw_template',
    description:
        'Guides Codex through context, validation, installation, and sync for '
        'one PTW schema-v3 template.',
    argsSchema: const {
      'intent': PromptArgumentDefinition(
        description: 'What story or share outcome the template should create.',
        required: true,
      ),
      'family': PromptArgumentDefinition(
        description: 'Optional target PTW template family.',
      ),
      'journeyState': PromptArgumentDefinition(
        description: 'Optional target PTW journey state.',
      ),
    },
    callback: (arguments, extra) async {
      final intent = arguments?['intent'] ?? '';
      final family = arguments?['family'];
      final journeyState = arguments?['journeyState'];
      return GetPromptResult(
        description: 'Author and install a validated PTW schema-v3 template.',
        messages: [
          PromptMessage(
            role: PromptMessageRole.user,
            content: TextContent(
              text: '''
Create a PTW schema-v3 template for this intent: $intent
${family == null ? '' : 'Preferred family: $family'}
${journeyState == null ? '' : 'Preferred journey state: $journeyState'}

Use only the PTW template generator MCP. First call get_template_context, then
iterate with validate_template. After validation succeeds, ask before calling
the write-class upsert_template tool. Do not generate Dart or external assets.
After installation, synchronize the runtime theme before running Flutter.
''',
            ),
          ),
        ],
      );
    },
  );

  return server;
}

Map<String, dynamic> _jsonObject(Object? value, String field) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  throw FormatException('$field must be a JSON object.');
}

Future<CallToolResult> _jsonResult(
  Future<Map<String, dynamic>> Function() operation,
) async {
  try {
    return CallToolResult.fromStructuredContent(await operation());
  } on Object catch (error) {
    final payload = <String, dynamic>{
      'protocolVersion': ptwTemplateGeneratorProtocolVersion,
      'error': error.toString(),
    };
    return CallToolResult(
      content: [TextContent(text: jsonEncode(payload))],
      structuredContent: payload,
      isError: true,
    );
  }
}
