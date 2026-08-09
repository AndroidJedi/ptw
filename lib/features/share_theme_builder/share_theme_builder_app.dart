import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../generated_share_editor/generated_share_editor.dart';
import 'ptw_template_validator.dart';
import 'share_theme_builder_web_io.dart';
import 'theme_builder_controller.dart';
import 'theme_builder_draft_migration.dart';
import 'theme_package_exporter.dart';

final class ShareThemeBuilderApp extends StatefulWidget {
  const ShareThemeBuilderApp({super.key});

  @override
  State<ShareThemeBuilderApp> createState() => _ShareThemeBuilderAppState();
}

final class _ShareThemeBuilderAppState extends State<ShareThemeBuilderApp> {
  static const _draftKey = 'ptw.share.theme.builder.draft.v1';
  late final Future<ThemeBuilderController> _load;
  final _preferences = SharedPreferencesAsync();
  Timer? _autosave;

  @override
  void initState() {
    super.initState();
    _load = _loadController();
  }

  Future<ThemeBuilderController> _loadController() async {
    final fallback = await ShareThemeBundle.loadAsset();
    final saved = await _preferences.getString(_draftKey);
    ShareThemeConfig theme = fallback;
    if (saved != null) {
      try {
        final restored = ShareThemeBundle.fromJsonString(saved);
        theme = migrateThemeBuilderDraft(saved: restored, bundled: fallback);
        if (!identical(theme, restored)) {
          await _preferences.setString(
            _draftKey,
            ShareThemeBundle.toJsonString(theme),
          );
        }
      } on FormatException {
        // An invalid local draft never prevents the builder from opening.
      }
    }
    return ThemeBuilderController(theme)..addListener(_scheduleAutosave);
  }

  void _scheduleAutosave() {
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 450), () async {
      final controller = await _load;
      await _preferences.setString(
        _draftKey,
        ShareThemeBundle.toJsonString(controller.theme),
      );
    });
  }

  @override
  void dispose() {
    _autosave?.cancel();
    _load.then((value) {
      value.removeListener(_scheduleAutosave);
      value.dispose();
    });
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Share Theme Builder',
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFFF4066E),
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xFF0C1220),
      fontFamily: 'PtwRoboto',
      useMaterial3: true,
    ),
    home: FutureBuilder<ThemeBuilderController>(
      future: _load,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Scaffold(
            body: Center(
              child: Text('Builder failed to load: ${snapshot.error}'),
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return ShareThemeBuilderScreen(controller: snapshot.requireData);
      },
    ),
  );
}

final class ShareThemeBuilderScreen extends StatefulWidget {
  const ShareThemeBuilderScreen({required this.controller, super.key});

  final ThemeBuilderController controller;

  @override
  State<ShareThemeBuilderScreen> createState() =>
      _ShareThemeBuilderScreenState();
}

final class _ShareThemeBuilderScreenState
    extends State<ShareThemeBuilderScreen> {
  final _exporter = ShareThemePackageExporter();
  bool _busy = false;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          AnimatedBuilder(
            animation: widget.controller,
            builder:
                (_, __) => _BuilderHeader(
                  controller: widget.controller,
                  busy: _busy,
                  onImport: _importJson,
                  onExport: _exportJson,
                  onGenerate: _generateZip,
                  onImportAsset: _importAsset,
                  onImportFont: _importFont,
                ),
          ),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final workspace = SizedBox(
                  width:
                      constraints.maxWidth < 1080 ? 1080 : constraints.maxWidth,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      SizedBox(
                        width: 270,
                        child: AnimatedBuilder(
                          animation: widget.controller,
                          builder:
                              (_, __) =>
                                  _LayersPane(controller: widget.controller),
                        ),
                      ),
                      Expanded(
                        child: _DesignCanvas(controller: widget.controller),
                      ),
                      SizedBox(
                        width: 360,
                        child: AnimatedBuilder(
                          animation: widget.controller,
                          builder:
                              (_, __) => _InspectorPane(
                                controller: widget.controller,
                                onUploadPhoto: _importAsset,
                              ),
                        ),
                      ),
                    ],
                  ),
                );
                if (constraints.maxWidth >= 1080) return workspace;
                return SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: workspace,
                );
              },
            ),
          ),
        ],
      ),
    ),
  );

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } on Object catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not complete that action: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _importJson() => _run(() async {
    final file = await ShareThemeBuilderWebIo.pickFile(
      accept: '.json,application/json',
    );
    if (file == null) return;
    widget.controller.replaceFromJson(utf8.decode(file.bytes));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Theme imported and validated')),
      );
    }
  });

  Future<void> _exportJson() => _run(() async {
    final json = await _exporter.portableJson(widget.controller.theme);
    ShareThemeBuilderWebIo.download(
      fileName: '${widget.controller.theme.id}.share-theme.json',
      bytes: utf8.encode(json),
      mimeType: 'application/json',
    );
    widget.controller.markSaved();
  });

  Future<void> _generateZip() => _run(() async {
    final validations = PtwTemplateValidator.validateTheme(
      widget.controller.theme,
    );
    final blocked = validations.where((result) => !result.isReady).toList();
    if (blocked.isNotEmpty) {
      throw StateError(
        'PTW validation failed for ${blocked.map((item) => item.template.label).join(', ')}',
      );
    }
    final package = await _exporter.generate(widget.controller.theme);
    ShareThemeBuilderWebIo.download(
      fileName: 'generated_share_editor.zip',
      bytes: package.zipBytes,
      mimeType: 'application/zip',
    );
    widget.controller.markSaved();
  });

  Future<void> _importAsset() => _run(() async {
    final file = await ShareThemeBuilderWebIo.pickFile(
      accept: '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp',
    );
    if (file == null) return;
    final assetId = await widget.controller.addAsset(
      fileName: file.name,
      mimeType: file.mimeType,
      bytes: file.bytes,
      kind: 'image',
    );
    widget.controller.addPhotoBackground(
      assetId,
      label: file.name.replaceFirst(RegExp(r'\.[^.]+$'), ''),
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Photo added to the reusable background gallery'),
        ),
      );
    }
  });

  Future<void> _importFont() => _run(() async {
    final file = await ShareThemeBuilderWebIo.pickFile(
      accept: '.ttf,.otf,font/ttf,font/otf',
    );
    if (file == null) return;
    final family = file.name.replaceFirst(RegExp(r'\.[^.]+$'), '');
    await widget.controller.addAsset(
      fileName: file.name,
      mimeType: file.mimeType,
      bytes: file.bytes,
      kind: 'font',
      fontFamily: family,
    );
  });
}

final class _BuilderHeader extends StatelessWidget {
  const _BuilderHeader({
    required this.controller,
    required this.busy,
    required this.onImport,
    required this.onExport,
    required this.onGenerate,
    required this.onImportAsset,
    required this.onImportFont,
  });

  final ThemeBuilderController controller;
  final bool busy;
  final VoidCallback onImport;
  final VoidCallback onExport;
  final VoidCallback onGenerate;
  final VoidCallback onImportAsset;
  final VoidCallback onImportFont;

  @override
  Widget build(BuildContext context) => Container(
    height: 66,
    padding: const EdgeInsets.symmetric(horizontal: 16),
    decoration: const BoxDecoration(
      color: Color(0xFF131B2E),
      border: Border(bottom: BorderSide(color: Color(0xFF27324D))),
    ),
    child: LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 1550;
        return Row(
          children: [
            Container(
              width: 38,
              height: 38,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: Color(0xFFF4066E),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.dashboard_customize_rounded,
                color: Colors.white,
              ),
            ),
            SizedBox(width: compact ? 6 : 11),
            if (compact)
              Expanded(
                child: Row(
                  children: [
                    Flexible(
                      child: Text(
                        controller.theme.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    if (controller.hasUnsavedChanges)
                      const Padding(
                        padding: EdgeInsets.only(left: 5),
                        child: Icon(
                          Icons.circle,
                          size: 7,
                          color: Color(0xFFFFE557),
                        ),
                      ),
                  ],
                ),
              )
            else
              Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        controller.theme.name,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if (controller.hasUnsavedChanges)
                        const Padding(
                          padding: EdgeInsets.only(left: 6),
                          child: Tooltip(
                            message: 'Unsaved export changes',
                            child: Icon(
                              Icons.circle,
                              size: 7,
                              color: Color(0xFFFFE557),
                            ),
                          ),
                        ),
                    ],
                  ),
                  Text(
                    '${controller.theme.canvas.outputWidth}×${controller.theme.canvas.outputHeight} · schema v${controller.theme.schemaVersion}',
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: Colors.white54),
                  ),
                ],
              ),
            SizedBox(width: compact ? 2 : 22),
            IconButton(
              tooltip: 'Undo',
              onPressed: controller.canUndo ? controller.undo : null,
              icon: const Icon(Icons.undo_rounded),
            ),
            IconButton(
              tooltip: 'Redo',
              onPressed: controller.canRedo ? controller.redo : null,
              icon: const Icon(Icons.redo_rounded),
            ),
            if (compact)
              IconButton(
                key: const ValueKey('builder_mode_toggle'),
                tooltip:
                    controller.mode == ThemeBuilderMode.explore
                        ? 'Switch to Production mode'
                        : 'Switch to Explore mode',
                onPressed:
                    () => controller.setMode(
                      controller.mode == ThemeBuilderMode.explore
                          ? ThemeBuilderMode.production
                          : ThemeBuilderMode.explore,
                    ),
                icon: Icon(
                  controller.mode == ThemeBuilderMode.explore
                      ? Icons.science_outlined
                      : Icons.verified_outlined,
                ),
              )
            else
              SegmentedButton<ThemeBuilderMode>(
                key: const ValueKey('builder_mode_segment'),
                segments: const [
                  ButtonSegment(
                    value: ThemeBuilderMode.explore,
                    label: Text('Explore'),
                    icon: Icon(Icons.science_outlined),
                  ),
                  ButtonSegment(
                    value: ThemeBuilderMode.production,
                    label: Text('Production'),
                    icon: Icon(Icons.verified_outlined),
                  ),
                ],
                selected: {controller.mode},
                onSelectionChanged: (value) => controller.setMode(value.first),
              ),
            if (!compact) const Spacer(),
            if (compact)
              TextButton.icon(
                onPressed:
                    () => controller.togglePremiumPreview(
                      !controller.previewPremium,
                    ),
                icon: Icon(
                  controller.previewPremium
                      ? Icons.workspace_premium
                      : Icons.person_outline,
                  color:
                      controller.previewPremium
                          ? const Color(0xFFFFE557)
                          : null,
                ),
                label: const Text('Premium'),
              )
            else
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(
                    value: false,
                    label: Text('Free'),
                    icon: Icon(Icons.person_outline),
                  ),
                  ButtonSegment(
                    value: true,
                    label: Text('Premium'),
                    icon: Icon(Icons.workspace_premium),
                  ),
                ],
                selected: {controller.previewPremium},
                onSelectionChanged:
                    (value) => controller.togglePremiumPreview(value.first),
              ),
            if (!compact) const SizedBox(width: 12),
            PopupMenuButton<String>(
              tooltip: 'Import assets',
              enabled: !busy,
              onSelected:
                  (value) => value == 'font' ? onImportFont() : onImportAsset(),
              itemBuilder:
                  (_) => const [
                    PopupMenuItem(
                      value: 'image',
                      child: Text('Import image asset'),
                    ),
                    PopupMenuItem(value: 'font', child: Text('Import font')),
                  ],
              icon: const Icon(Icons.add_photo_alternate_outlined),
            ),
            IconButton(
              tooltip: 'Import JSON',
              onPressed: busy ? null : onImport,
              icon: const Icon(Icons.file_open_outlined),
            ),
            IconButton(
              tooltip: 'Export portable JSON',
              onPressed: busy ? null : onExport,
              icon: const Icon(Icons.data_object_rounded),
            ),
            if (!compact) const SizedBox(width: 8),
            if (compact)
              IconButton(
                key: const ValueKey('builder_generate_zip'),
                tooltip: 'Generate ZIP',
                onPressed: busy ? null : onGenerate,
                icon:
                    busy
                        ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Icon(Icons.folder_zip_outlined),
              )
            else
              FilledButton.icon(
                key: const ValueKey('builder_generate_zip'),
                onPressed: busy ? null : onGenerate,
                icon:
                    busy
                        ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Icon(Icons.folder_zip_outlined),
                label: const Text('Generate ZIP'),
              ),
          ],
        );
      },
    ),
  );
}

final class _LayersPane extends StatelessWidget {
  const _LayersPane({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      color: Color(0xFF11192A),
      border: Border(right: BorderSide(color: Color(0xFF27324D))),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _PaneTitle(title: 'TEMPLATES'),
        Padding(
          padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
          child: DropdownButtonFormField<String>(
            key: const ValueKey('builder_template_picker'),
            value: controller.selectedTemplateId,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Structure',
              isDense: true,
            ),
            items: [
              for (final template in controller.theme.templates)
                DropdownMenuItem(
                  value: template.id,
                  child: Text(template.label),
                ),
            ],
            onChanged:
                (value) =>
                    value == null ? null : controller.selectTemplate(value),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: Text(
            controller.mode == ThemeBuilderMode.production
                ? 'Production edits change this template structure.'
                : 'Explore edits change reusable base layers and looks.',
            style: const TextStyle(color: Colors.white54, fontSize: 10),
          ),
        ),
        const Divider(height: 1),
        _PaneTitle(
          title: 'LOOKS',
          trailing: IconButton(
            tooltip: 'Add look',
            onPressed:
                controller.mode == ThemeBuilderMode.explore
                    ? controller.addLook
                    : null,
            icon: const Icon(Icons.add_rounded, size: 19),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(
            children: [
              Expanded(
                child: _VisualPickerField<String>(
                  key: const ValueKey('builder_look_visual_picker'),
                  label: 'Look',
                  value: controller.selectedLookId,
                  selectedLabel: controller.selectedLook.label,
                  selectedPreview: _ThemePreviewThumbnail(
                    theme: controller.theme,
                    lookId: controller.selectedLookId,
                  ),
                  options: [
                    for (final look in controller.theme.looks)
                      _VisualPickerOption(
                        value: look.id,
                        label: look.label,
                        subtitle: look.id,
                        preview: _ThemePreviewThumbnail(
                          theme: controller.theme,
                          lookId: look.id,
                        ),
                      ),
                  ],
                  onChanged: controller.selectLook,
                ),
              ),
              IconButton(
                tooltip: 'Delete look',
                onPressed:
                    controller.theme.looks.length > 1 &&
                            controller.mode == ThemeBuilderMode.explore
                        ? controller.removeSelectedLook
                        : null,
                icon: const Icon(Icons.delete_outline_rounded),
              ),
            ],
          ),
        ),
        SwitchListTile.adaptive(
          dense: true,
          title: const Text(
            'Edit this look only',
            style: TextStyle(fontSize: 12),
          ),
          value: controller.editLookOverrides,
          onChanged:
              controller.mode == ThemeBuilderMode.explore
                  ? controller.toggleLookOverrides
                  : null,
        ),
        const Divider(height: 1),
        _PaneTitle(
          title: 'LAYERS',
          trailing: PopupMenuButton<String>(
            tooltip: 'Add component',
            onSelected: controller.addLayer,
            itemBuilder:
                (_) => const [
                  PopupMenuItem(value: 'text', child: Text('Text / label')),
                  PopupMenuItem(value: 'image', child: Text('Photo / avatar')),
                  PopupMenuItem(value: 'asset', child: Text('Static asset')),
                  PopupMenuItem(value: 'shape', child: Text('Shape')),
                  PopupMenuItem(
                    value: 'stickerWorkspace',
                    child: Text('Sticker workspace'),
                  ),
                ],
            icon: const Icon(Icons.add_box_outlined, size: 19),
          ),
        ),
        Expanded(
          child: ReorderableListView.builder(
            padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
            buildDefaultDragHandles: false,
            itemExtent: 44,
            itemCount: controller.theme.layers.length,
            onReorder: (oldIndex, newIndex) {
              final adjusted = newIndex > oldIndex ? newIndex - 1 : newIndex;
              controller.selectLayer(controller.theme.layers[oldIndex].id);
              controller.moveSelectedLayer(adjusted - oldIndex);
            },
            itemBuilder: (context, index) {
              final layer = controller.theme.layers[index];
              final selected = controller.selectedLayerId == layer.id;
              return Material(
                key: ValueKey(layer.id),
                color:
                    selected
                        ? const Color(0xFF2C385A)
                        : const Color(0xFF192238),
                borderRadius: BorderRadius.circular(8),
                child: InkWell(
                  borderRadius: BorderRadius.circular(8),
                  onTap: () => controller.selectLayer(layer.id),
                  child: Semantics(
                    label: '${layer.label}, ${layer.type} layer',
                    selected: selected,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: Row(
                        children: [
                          Tooltip(
                            message: '${layer.type} component',
                            child: Icon(_layerIcon(layer.type), size: 18),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              layer.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                          ReorderableDragStartListener(
                            index: index,
                            child: const Padding(
                              padding: EdgeInsets.all(4),
                              child: Icon(
                                Icons.drag_indicator_rounded,
                                size: 18,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              IconButton(
                tooltip: 'Move layer down',
                onPressed: () => controller.moveSelectedLayer(-1),
                icon: const Icon(Icons.arrow_downward_rounded),
              ),
              IconButton(
                tooltip: 'Move layer up',
                onPressed: () => controller.moveSelectedLayer(1),
                icon: const Icon(Icons.arrow_upward_rounded),
              ),
              const Spacer(),
              IconButton(
                tooltip: 'Delete layer',
                onPressed: controller.removeSelectedLayer,
                icon: const Icon(Icons.delete_outline_rounded),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

final class _DesignCanvas extends StatefulWidget {
  const _DesignCanvas({required this.controller});

  final ThemeBuilderController controller;

  @override
  State<_DesignCanvas> createState() => _DesignCanvasState();
}

final class _DesignCanvasState extends State<_DesignCanvas> {
  late ShareEditorController _preview;
  late ShareEditorContent _content;
  ShareThemeConfig? _previewTheme;
  bool? _previewPremium;
  final _canvasFocus = FocusNode(debugLabel: 'share theme canvas');
  bool _previewReady = false;

  @override
  void initState() {
    super.initState();
    _rebuildPreview();
    widget.controller.addListener(_handleControllerChanged);
  }

  @override
  void didUpdateWidget(_DesignCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller == widget.controller) return;
    oldWidget.controller.removeListener(_handleControllerChanged);
    widget.controller.addListener(_handleControllerChanged);
    _rebuildPreview();
  }

  void _handleControllerChanged() {
    final controller = widget.controller;
    if (!identical(_previewTheme, controller.theme) ||
        _previewPremium != controller.previewPremium) {
      _rebuildPreview();
    } else {
      if (_preview.value.lookId != controller.selectedLookId) {
        _preview.selectLook(controller.selectedLookId);
      }
      if (_preview.value.templateId != controller.selectedTemplateId) {
        _preview.selectTemplate(controller.selectedTemplateId);
      }
    }
    if (mounted) setState(() {});
  }

  void _rebuildPreview() {
    if (_previewReady) _preview.dispose();
    _content = _sampleEditorContent(widget.controller.theme);
    _preview = ShareEditorController(
      theme: widget.controller.theme,
      content: _content,
      entitlements: (_) => widget.controller.previewPremium,
    );
    _preview.selectLook(widget.controller.selectedLookId);
    _preview.selectTemplate(widget.controller.selectedTemplateId);
    _previewTheme = widget.controller.theme;
    _previewPremium = widget.controller.previewPremium;
    _previewReady = true;
  }

  @override
  void dispose() {
    widget.controller.removeListener(_handleControllerChanged);
    _preview.dispose();
    _canvasFocus.dispose();
    super.dispose();
  }

  void _handleKey(KeyEvent event) {
    if (widget.controller.previewOnly) return;
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) return;
    final layer = widget.controller.editingLayer;
    if (layer == null) return;
    final distance = HardwareKeyboard.instance.isShiftPressed ? 10.0 : 1.0;
    final delta = switch (event.logicalKey) {
      LogicalKeyboardKey.arrowLeft => Offset(-distance, 0),
      LogicalKeyboardKey.arrowRight => Offset(distance, 0),
      LogicalKeyboardKey.arrowUp => Offset(0, -distance),
      LogicalKeyboardKey.arrowDown => Offset(0, distance),
      _ => null,
    };
    if (delta == null) return;
    widget.controller.updateSelectedTransform(
      layer.transform.copyWith(
        x: layer.transform.x + delta.dx,
        y: layer.transform.y + delta.dy,
      ),
    );
  }

  @override
  Widget build(BuildContext context) => KeyboardListener(
    focusNode: _canvasFocus,
    autofocus: true,
    onKeyEvent: _handleKey,
    child: ColoredBox(
      color: const Color(0xFF090E19),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
            child: Row(
              children: [
                SegmentedButton<bool>(
                  key: const ValueKey('builder_preview_mode_toggle'),
                  segments: const [
                    ButtonSegment(
                      value: false,
                      label: Text('Edit'),
                      icon: Icon(Icons.edit_outlined, size: 16),
                    ),
                    ButtonSegment(
                      value: true,
                      label: Text('Preview'),
                      icon: Icon(Icons.visibility_outlined, size: 16),
                    ),
                  ],
                  selected: {widget.controller.previewOnly},
                  onSelectionChanged:
                      (value) =>
                          widget.controller.togglePreviewOnly(value.first),
                  showSelectedIcon: false,
                  style: const ButtonStyle(
                    visualDensity: VisualDensity.compact,
                  ),
                ),
                const Spacer(),
                IconButton(
                  key: const ValueKey('builder_safe_zone_toggle'),
                  visualDensity: VisualDensity.compact,
                  tooltip:
                      widget.controller.showSafeZones
                          ? 'Hide PTW safe zones'
                          : 'Show PTW safe zones',
                  onPressed:
                      widget.controller.previewOnly
                          ? null
                          : () => widget.controller.toggleSafeZones(
                            !widget.controller.showSafeZones,
                          ),
                  color:
                      widget.controller.showSafeZones &&
                              !widget.controller.previewOnly
                          ? const Color(0xFF66E3A4)
                          : Colors.white38,
                  icon: const Icon(Icons.safety_check_outlined, size: 18),
                ),
                IconButton(
                  key: const ValueKey('builder_grid_toggle'),
                  visualDensity: VisualDensity.compact,
                  tooltip:
                      widget.controller.showGrid ? 'Hide grid' : 'Show grid',
                  onPressed:
                      widget.controller.previewOnly
                          ? null
                          : () => widget.controller.updateGrid(
                            visible: !widget.controller.showGrid,
                          ),
                  color:
                      widget.controller.showGrid &&
                              !widget.controller.previewOnly
                          ? const Color(0xFFFFE557)
                          : Colors.white38,
                  icon: const Icon(Icons.grid_on_rounded, size: 18),
                ),
                IconButton(
                  key: const ValueKey('builder_snap_toggle'),
                  visualDensity: VisualDensity.compact,
                  tooltip:
                      widget.controller.snapToGrid
                          ? 'Disable grid snapping'
                          : 'Enable grid snapping',
                  onPressed:
                      widget.controller.previewOnly
                          ? null
                          : () => widget.controller.updateGrid(
                            snap: !widget.controller.snapToGrid,
                          ),
                  color:
                      widget.controller.snapToGrid
                          ? const Color(0xFFFFE557)
                          : Colors.white38,
                  icon: const Icon(Icons.grid_4x4_rounded, size: 18),
                ),
                PopupMenuButton<double>(
                  key: const ValueKey('builder_grid_size'),
                  tooltip: 'Grid spacing',
                  onSelected:
                      (value) => widget.controller.updateGrid(size: value),
                  itemBuilder:
                      (_) => [
                        for (final size in const [10.0, 20.0, 40.0, 80.0])
                          PopupMenuItem(
                            value: size,
                            child: Text('${size.toInt()} logical pixels'),
                          ),
                      ],
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 5),
                    child: Text(
                      '${widget.controller.gridSize.toInt()}',
                      style: const TextStyle(
                        color: Colors.white54,
                        fontSize: 11,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final canvas = widget.controller.theme.canvas;
                final width = (constraints.maxHeight *
                        canvas.width /
                        canvas.height)
                    .clamp(200.0, constraints.maxWidth - 56);
                final height = width * canvas.height / canvas.width;
                final scale = width / canvas.width;
                final selectedLayer = widget.controller.editingLayer;
                final selectedStickerId =
                    widget.controller.selectedLookStickerId;
                return Center(
                  child: Container(
                    width: width,
                    height: height,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(
                        widget.controller.theme.canvas.cornerRadius * scale,
                      ),
                      border: Border.all(color: Colors.white24),
                      boxShadow: const [
                        BoxShadow(color: Colors.black87, blurRadius: 30),
                      ],
                    ),
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: RepaintBoundary(
                            child: GeneratedShareRenderer(
                              key: const ValueKey('builder_live_renderer'),
                              theme: widget.controller.theme,
                              content: _content,
                              value: _preview.value,
                              controller: _preview,
                              interactionEnabled: false,
                              isolateRepaints: true,
                              showSelection: false,
                              liveLayerId: widget.controller.selectedLayerId,
                              liveLayerDraft: widget.controller.liveLayerDraft,
                              liveStickerDraft:
                                  widget.controller.liveStickerDraft,
                              liveBackgroundTreatmentDraft:
                                  widget
                                      .controller
                                      .liveBackgroundTreatmentDraft,
                              liveBackgroundDraft:
                                  widget.controller.liveBackgroundDraft,
                              showAuthoringGuides:
                                  widget.controller.showSafeZones &&
                                  !widget.controller.previewOnly,
                            ),
                          ),
                        ),
                        if (widget.controller.showGrid &&
                            !widget.controller.previewOnly)
                          Positioned.fill(
                            child: IgnorePointer(
                              child: RepaintBoundary(
                                child: CustomPaint(
                                  key: const ValueKey('builder_canvas_grid'),
                                  painter: _CanvasGridPainter(
                                    logicalStep: widget.controller.gridSize,
                                    scale: scale,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        if (!widget.controller.previewOnly)
                          for (final layer in widget.controller.theme.layers)
                            if (layer.id != widget.controller.selectedLayerId &&
                                layer.type != 'background' &&
                                layer.type != 'stickerWorkspace' &&
                                _preview.effectiveLayer(layer.id).visible)
                              _BuilderLayerOverlay(
                                key: ValueKey(
                                  'builder_layer_overlay_${layer.id}',
                                ),
                                controller: widget.controller,
                                layer: _preview.effectiveLayer(layer.id),
                                scale: scale,
                                selected: false,
                                onSelect: () {
                                  _canvasFocus.requestFocus();
                                  widget.controller.selectLayer(layer.id);
                                },
                              ),
                        if (!widget.controller.previewOnly)
                          for (final sticker
                              in widget.controller.selectedLook.defaultStickers)
                            if (sticker.instanceId != selectedStickerId)
                              _BuilderStickerOverlay(
                                key: ValueKey(
                                  'builder_sticker_overlay_${sticker.instanceId}',
                                ),
                                controller: widget.controller,
                                sticker: sticker,
                                workspace: _effectiveStickerWorkspace(
                                  widget.controller,
                                  _preview,
                                ),
                                scale: scale,
                              ),
                        if (!widget.controller.previewOnly &&
                            selectedLayer != null &&
                            selectedLayer.visible &&
                            selectedLayer.type != 'background' &&
                            selectedLayer.type != 'stickerWorkspace')
                          ValueListenableBuilder<ShareLayerConfig?>(
                            valueListenable: widget.controller.liveLayerDraft,
                            builder: (_, draft, __) {
                              final liveLayer =
                                  draft?.id == selectedLayer.id
                                      ? draft!
                                      : selectedLayer;
                              return _BuilderLayerOverlay(
                                key: ValueKey(
                                  'builder_layer_overlay_${selectedLayer.id}',
                                ),
                                controller: widget.controller,
                                layer: liveLayer,
                                scale: scale,
                                selected: true,
                                onSelect: () {
                                  _canvasFocus.requestFocus();
                                  widget.controller.selectLayer(
                                    selectedLayer.id,
                                  );
                                },
                              );
                            },
                          ),
                        if (!widget.controller.previewOnly &&
                            selectedStickerId != null)
                          ValueListenableBuilder<ShareStickerValue?>(
                            valueListenable: widget.controller.liveStickerDraft,
                            builder: (_, draft, __) {
                              final sticker =
                                  draft?.instanceId == selectedStickerId
                                      ? draft!
                                      : widget
                                          .controller
                                          .selectedLook
                                          .defaultStickers
                                          .firstWhere(
                                            (item) =>
                                                item.instanceId ==
                                                selectedStickerId,
                                          );
                              return _BuilderStickerOverlay(
                                key: ValueKey(
                                  'builder_sticker_overlay_$selectedStickerId',
                                ),
                                controller: widget.controller,
                                sticker: sticker,
                                workspace: _effectiveStickerWorkspace(
                                  widget.controller,
                                  _preview,
                                ),
                                scale: scale,
                              );
                            },
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    ),
  );
}

final class _BuilderLayerOverlay extends StatefulWidget {
  const _BuilderLayerOverlay({
    required this.controller,
    required this.layer,
    required this.scale,
    required this.selected,
    required this.onSelect,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;
  final double scale;
  final bool selected;
  final VoidCallback onSelect;

  @override
  State<_BuilderLayerOverlay> createState() => _BuilderLayerOverlayState();
}

final class _BuilderLayerOverlayState extends State<_BuilderLayerOverlay> {
  final _frameKey = GlobalKey();

  double _pointerAngle(Offset globalPosition) {
    final renderObject = _frameKey.currentContext?.findRenderObject();
    if (renderObject is! RenderBox) return 0;
    final center = renderObject.localToGlobal(
      renderObject.size.center(Offset.zero),
    );
    return math.atan2(
      globalPosition.dy - center.dy,
      globalPosition.dx - center.dx,
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final layer = widget.layer;
    final scale = widget.scale;
    final selected = widget.selected;
    final onSelect = widget.onSelect;
    final transform = layer.transform;
    return Positioned(
      left: transform.x * scale,
      top: transform.y * scale,
      width: transform.width * scale,
      height: transform.height * scale,
      child: Transform.rotate(
        angle: transform.rotation,
        child: MouseRegion(
          cursor: SystemMouseCursors.move,
          child: GestureDetector(
            key: ValueKey('builder_canvas_layer_${layer.id}'),
            behavior: HitTestBehavior.translucent,
            onTap: onSelect,
            onPanDown: (_) => onSelect(),
            onPanStart: (_) => controller.beginSelectedLayerTransform(),
            onPanUpdate:
                (details) => controller.moveSelectedLayerBy(
                  deltaX: details.delta.dx / scale,
                  deltaY: details.delta.dy / scale,
                ),
            onPanEnd: (_) => controller.finishSelectedLayerTransform(),
            onPanCancel: controller.cancelSelectedLayerTransform,
            child: SizedBox.expand(
              key: _frameKey,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        border:
                            selected
                                ? Border.all(
                                  color: const Color(0xFFFFE557),
                                  width: 2,
                                )
                                : Border.all(color: Colors.transparent),
                      ),
                    ),
                  ),
                  if (selected) ...[
                    Positioned(
                      right: -8,
                      bottom: -8,
                      child: MouseRegion(
                        cursor: SystemMouseCursors.resizeUpLeftDownRight,
                        child: GestureDetector(
                          key: ValueKey('builder_resize_layer_${layer.id}'),
                          behavior: HitTestBehavior.opaque,
                          onPanStart:
                              (_) => controller.beginSelectedLayerTransform(),
                          onPanUpdate:
                              (details) => controller.resizeSelectedLayerBy(
                                deltaWidth: details.delta.dx / scale,
                                deltaHeight: details.delta.dy / scale,
                              ),
                          onPanEnd:
                              (_) => controller.finishSelectedLayerTransform(),
                          onPanCancel: controller.cancelSelectedLayerTransform,
                          child: const _CanvasHandle(
                            icon: Icons.open_in_full_rounded,
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      right: -8,
                      top: -8,
                      child: MouseRegion(
                        cursor: SystemMouseCursors.grab,
                        child: GestureDetector(
                          key: ValueKey('builder_rotate_layer_${layer.id}'),
                          behavior: HitTestBehavior.opaque,
                          onPanStart:
                              (details) =>
                                  controller.beginSelectedLayerRotation(
                                    _pointerAngle(details.globalPosition),
                                  ),
                          onPanUpdate:
                              (details) => controller.rotateSelectedLayerTo(
                                _pointerAngle(details.globalPosition),
                              ),
                          onPanEnd:
                              (_) => controller.finishSelectedLayerTransform(),
                          onPanCancel: controller.cancelSelectedLayerTransform,
                          child: const _CanvasHandle(
                            icon: Icons.rotate_right_rounded,
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

final class _CanvasHandle extends StatelessWidget {
  const _CanvasHandle({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    width: 24,
    height: 24,
    alignment: Alignment.center,
    decoration: const BoxDecoration(
      color: Color(0xFFFFE557),
      shape: BoxShape.circle,
    ),
    child: Icon(icon, size: 14, color: Colors.black),
  );
}

final class _CanvasGridPainter extends CustomPainter {
  const _CanvasGridPainter({required this.logicalStep, required this.scale});

  final double logicalStep;
  final double scale;

  @override
  void paint(Canvas canvas, Size size) {
    final step = logicalStep * 10 * scale;
    if (!step.isFinite || step < 2) return;
    final guide =
        Paint()
          ..color = const Color(0xFFFFE557).withValues(alpha: 0.22)
          ..strokeWidth = 0.8;
    for (var x = 0.0; x <= size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), guide);
    }
    for (var y = 0.0; y <= size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), guide);
    }
    final centerGuide =
        Paint()
          ..color = const Color(0xFF61DAFB).withValues(alpha: 0.88)
          ..strokeWidth = 1.4;
    final centerX = size.width / 2;
    final centerY = size.height / 2;
    canvas.drawLine(
      Offset(centerX, 0),
      Offset(centerX, size.height),
      centerGuide,
    );
    canvas.drawLine(
      Offset(0, centerY),
      Offset(size.width, centerY),
      centerGuide,
    );
    canvas.drawCircle(
      Offset(centerX, centerY),
      4,
      Paint()
        ..color = const Color(0xFF61DAFB)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4,
    );
  }

  @override
  bool shouldRepaint(_CanvasGridPainter oldDelegate) =>
      oldDelegate.logicalStep != logicalStep || oldDelegate.scale != scale;
}

final class _VisualPickerOption<T> {
  const _VisualPickerOption({
    required this.value,
    required this.label,
    required this.preview,
    this.subtitle,
  });

  final T value;
  final String label;
  final String? subtitle;
  final Widget preview;
}

final class _VisualPickerField<T> extends StatelessWidget {
  const _VisualPickerField({
    required this.label,
    required this.value,
    required this.selectedLabel,
    required this.selectedPreview,
    required this.options,
    required this.onChanged,
    super.key,
  });

  final String label;
  final T value;
  final String selectedLabel;
  final Widget selectedPreview;
  final List<_VisualPickerOption<T>> options;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: options.isEmpty ? null : () => _open(context),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          suffixIcon: const Icon(Icons.expand_more_rounded),
        ),
        child: SizedBox(
          height: 58,
          child: Row(
            children: [
              SizedBox.square(dimension: 52, child: selectedPreview),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  selectedLabel,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );

  Future<void> _open(BuildContext context) async {
    final selected = await showDialog<T>(
      context: context,
      builder:
          (dialogContext) => Dialog(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760, maxHeight: 680),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Choose $label',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                        ),
                        IconButton(
                          tooltip: 'Close',
                          onPressed: () => Navigator.pop(dialogContext),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Expanded(
                      child: GridView.builder(
                        key: ValueKey('builder_visual_picker_grid_$label'),
                        gridDelegate:
                            const SliverGridDelegateWithMaxCrossAxisExtent(
                              maxCrossAxisExtent: 180,
                              mainAxisSpacing: 10,
                              crossAxisSpacing: 10,
                              childAspectRatio: 0.82,
                            ),
                        itemCount: options.length,
                        itemBuilder: (context, index) {
                          final option = options[index];
                          final isSelected = option.value == value;
                          return Card(
                            clipBehavior: Clip.antiAlias,
                            color:
                                isSelected
                                    ? const Color(0xFF2C385A)
                                    : const Color(0xFF192238),
                            shape: RoundedRectangleBorder(
                              side: BorderSide(
                                color:
                                    isSelected
                                        ? const Color(0xFFFFE557)
                                        : Colors.white12,
                                width: isSelected ? 2 : 1,
                              ),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: InkWell(
                              key: ValueKey(
                                'builder_visual_option_${option.value}',
                              ),
                              onTap:
                                  () => Navigator.pop(
                                    dialogContext,
                                    option.value,
                                  ),
                              child: Padding(
                                padding: const EdgeInsets.all(8),
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(
                                      child: ClipRRect(
                                        borderRadius: BorderRadius.circular(8),
                                        child: ColoredBox(
                                          color: Colors.black26,
                                          child: Center(child: option.preview),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(height: 7),
                                    Text(
                                      option.label,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    if (option.subtitle != null)
                                      Text(
                                        option.subtitle!,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          color: Colors.white54,
                                          fontSize: 11,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
    );
    if (selected != null) onChanged(selected);
  }
}

final class _ThemePreviewThumbnail extends StatefulWidget {
  const _ThemePreviewThumbnail({
    required this.theme,
    required this.lookId,
    this.backgroundId,
  });

  final ShareThemeConfig theme;
  final String lookId;
  final String? backgroundId;

  @override
  State<_ThemePreviewThumbnail> createState() => _ThemePreviewThumbnailState();
}

final class _ThemePreviewThumbnailState extends State<_ThemePreviewThumbnail> {
  late ShareEditorContent _content;
  late ShareEditorController _controller;
  late ShareEditorValue _value;

  @override
  void initState() {
    super.initState();
    _createPreview();
  }

  @override
  void didUpdateWidget(_ThemePreviewThumbnail oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.theme != widget.theme ||
        oldWidget.lookId != widget.lookId ||
        oldWidget.backgroundId != widget.backgroundId) {
      _controller.dispose();
      _createPreview();
    }
  }

  void _createPreview() {
    _content = _sampleEditorContent(widget.theme);
    _controller = ShareEditorController(
      theme: widget.theme,
      content: _content,
      entitlements: (_) => true,
    )..selectLook(widget.lookId);
    _value = _controller.value.copyWith(backgroundId: widget.backgroundId);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFF090E19),
    child: Center(
      child: AspectRatio(
        aspectRatio: widget.theme.canvas.width / widget.theme.canvas.height,
        child: IgnorePointer(
          child: GeneratedShareRenderer(
            theme: widget.theme,
            content: _content,
            value: _value,
          ),
        ),
      ),
    ),
  );
}

final class _FontPreview extends StatelessWidget {
  const _FontPreview({required this.family});

  final String family;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFF202A42),
    child: Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 5),
        child: Text(
          'Aa',
          style: TextStyle(
            fontFamily: family,
            fontSize: 27,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
      ),
    ),
  );
}

final class _BoundImagePreview extends StatelessWidget {
  const _BoundImagePreview({required this.binding});

  final String binding;

  @override
  Widget build(BuildContext context) => Image.asset(
    binding == 'avatar'
        ? 'assets/images/users/alex.jpg'
        : 'assets/images/backgrounds/startup.jpg',
    fit: BoxFit.cover,
    errorBuilder:
        (_, __, ___) => const ColoredBox(
          color: Color(0xFF202A42),
          child: Icon(Icons.person_outline_rounded),
        ),
  );
}

final class _ImageAssetPickerField extends StatelessWidget {
  const _ImageAssetPickerField({
    required this.theme,
    required this.label,
    required this.assetId,
    required this.emptyLabel,
    required this.onChanged,
    super.key,
  });

  static const _none = '__none__';

  final ShareThemeConfig theme;
  final String label;
  final String? assetId;
  final String emptyLabel;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    final selected =
        assetId == null
            ? null
            : theme.assets
                .where((item) => item.kind == 'image' && item.id == assetId)
                .firstOrNull;
    return _VisualPickerField<String>(
      label: label,
      value: selected?.id ?? _none,
      selectedLabel: selected?.id ?? emptyLabel,
      selectedPreview:
          selected == null
              ? const _EmptyVisualPreview(icon: Icons.hide_image_outlined)
              : _AssetThumbnail(asset: selected, size: 54),
      options: [
        _VisualPickerOption(
          value: _none,
          label: emptyLabel,
          preview: const _EmptyVisualPreview(icon: Icons.hide_image_outlined),
        ),
        for (final asset in theme.assets)
          if (asset.kind == 'image')
            _VisualPickerOption(
              value: asset.id,
              label: asset.id,
              subtitle: asset.mimeType,
              preview: _AssetThumbnail(asset: asset, size: 110),
            ),
      ],
      onChanged: (value) => onChanged(value == _none ? null : value),
    );
  }
}

final class _EmptyVisualPreview extends StatelessWidget {
  const _EmptyVisualPreview({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFF202A42),
    child: Center(child: Icon(icon, color: Colors.white54)),
  );
}

final class _IconPickerField extends StatelessWidget {
  const _IconPickerField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  static const values = [
    'palette',
    'image',
    'sticker',
    'tune',
    'magic',
    'workspace_premium',
    'lock',
    'diamond',
    'star',
    'text',
  ];

  final String label;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => _VisualPickerField<String>(
    label: label,
    value: value,
    selectedLabel: value,
    selectedPreview: _IconPreview(value: value),
    options: [
      for (final icon in values)
        _VisualPickerOption(
          value: icon,
          label: icon.replaceAll('_', ' '),
          preview: _IconPreview(value: icon),
        ),
    ],
    onChanged: onChanged,
  );
}

final class _IconPreview extends StatelessWidget {
  const _IconPreview({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFF202A42),
    child: Center(
      child: Icon(
        _namedBuilderIcon(value),
        size: 30,
        color: const Color(0xFFFFB0C8),
      ),
    ),
  );
}

ShareEditorContent _sampleEditorContent(ShareThemeConfig theme) {
  final sample = theme.sampleContent;
  return ShareEditorContent(
    projectId: '${sample['projectId'] ?? 'sample_project'}',
    headline: '${sample['headline'] ?? 'Your headline'}',
    secondaryText: '${sample['secondaryText'] ?? 'Your supporting text'}',
    ownerName: '${sample['ownerName'] ?? 'Alex'}',
    ownerHandle: '${sample['ownerHandle'] ?? 'alexbuilds'}',
    avatar: const ShareImageValue.asset('assets/images/users/alex.jpg'),
    cover: const ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
    caption: '${sample['caption'] ?? ''}',
    publicLink: '${sample['publicLink'] ?? 'https://ptw.to'}',
    previousMedia: const ShareImageValue.asset(
      'assets/images/backgrounds/fitness.jpg',
    ),
    currentMedia: const ShareImageValue.asset(
      'assets/images/backgrounds/startup.jpg',
    ),
    progressValue: '${sample['progressValue'] ?? '68%'}',
    metricValue: '${sample['metricValue'] ?? '+12 this week'}',
    previousTimeLabel: '${sample['previousTimeLabel'] ?? 'BEFORE'}',
    currentTimeLabel: '${sample['currentTimeLabel'] ?? 'NOW'}',
    proofLabel: '${sample['proofLabel'] ?? 'CONSISTENCY'}',
    custom: sample,
  );
}

List<String> _fontFamilies(ShareThemeConfig theme) {
  final families = <String>{'PtwRoboto', 'PtwLilitaOne'};
  for (final asset in theme.assets) {
    if (asset.kind == 'font' && asset.fontFamily?.trim().isNotEmpty == true) {
      families.add(asset.fontFamily!.trim());
    }
  }
  for (final layer in theme.layers) {
    final family = layer.style['fontFamily'];
    if (family is String && family.trim().isNotEmpty) {
      families.add(family.trim());
    }
  }
  return families.toList()..sort();
}

ShareLayerConfig _effectiveStickerWorkspace(
  ThemeBuilderController controller,
  ShareEditorController preview,
) {
  final workspace = controller.theme.layers.firstWhere(
    (item) => item.type == 'stickerWorkspace',
  );
  return preview.effectiveLayer(workspace.id);
}

final class _BuilderStickerOverlay extends StatelessWidget {
  const _BuilderStickerOverlay({
    required this.controller,
    required this.sticker,
    required this.workspace,
    required this.scale,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareStickerValue sticker;
  final ShareLayerConfig workspace;
  final double scale;

  @override
  Widget build(BuildContext context) {
    final transform = workspace.transform;
    final side = transform.width * sticker.scale;
    final selected = controller.selectedLookStickerId == sticker.instanceId;
    return Positioned(
      left:
          (transform.x + transform.width * sticker.centerX - side / 2) * scale,
      top:
          (transform.y + transform.height * sticker.centerY - side / 2) * scale,
      width: side * scale,
      height: side * scale,
      child: Transform.rotate(
        angle: sticker.rotation,
        child: MouseRegion(
          cursor: SystemMouseCursors.move,
          child: GestureDetector(
            key: ValueKey('builder_canvas_sticker_${sticker.instanceId}'),
            behavior: HitTestBehavior.opaque,
            onTap: () => controller.selectLookSticker(sticker.instanceId),
            onPanDown: (_) => controller.selectLookSticker(sticker.instanceId),
            onPanStart:
                (_) => controller.beginLookStickerTransform(sticker.instanceId),
            onPanUpdate:
                (details) => controller.moveLookStickerBy(
                  sticker.instanceId,
                  deltaX: details.delta.dx / scale,
                  deltaY: details.delta.dy / scale,
                  workspace: transform,
                ),
            onPanEnd:
                (_) =>
                    controller.finishLookStickerTransform(workspace: transform),
            onPanCancel: controller.cancelLookStickerTransform,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      border:
                          selected
                              ? Border.all(
                                color: const Color(0xFFFFE557),
                                width: 2,
                              )
                              : null,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                ),
                if (selected) ...[
                  Positioned(
                    left: -8,
                    top: -8,
                    child: GestureDetector(
                      key: ValueKey(
                        'builder_delete_sticker_${sticker.instanceId}',
                      ),
                      onTap:
                          () =>
                              controller.removeLookSticker(sticker.instanceId),
                      child: const _CanvasHandle(icon: Icons.close_rounded),
                    ),
                  ),
                  Positioned(
                    right: -8,
                    bottom: -8,
                    child: MouseRegion(
                      cursor: SystemMouseCursors.resizeUpLeftDownRight,
                      child: GestureDetector(
                        key: ValueKey(
                          'builder_transform_sticker_${sticker.instanceId}',
                        ),
                        behavior: HitTestBehavior.opaque,
                        onPanStart:
                            (_) => controller.beginLookStickerTransform(
                              sticker.instanceId,
                            ),
                        onPanUpdate:
                            (details) => controller.transformLookStickerBy(
                              sticker.instanceId,
                              scaleDelta:
                                  details.delta.dx / (scale * transform.width),
                              rotationDelta: details.delta.dy * 0.012,
                            ),
                        onPanEnd:
                            (_) => controller.finishLookStickerTransform(
                              workspace: transform,
                            ),
                        onPanCancel: controller.cancelLookStickerTransform,
                        child: const _CanvasHandle(icon: Icons.sync_rounded),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

final class _InspectorPane extends StatelessWidget {
  const _InspectorPane({required this.controller, required this.onUploadPhoto});

  final ThemeBuilderController controller;
  final VoidCallback onUploadPhoto;

  @override
  Widget build(BuildContext context) =>
      ValueListenableBuilder<ShareLayerConfig?>(
        valueListenable: controller.liveLayerDraft,
        builder:
            (_, __, ___) => ValueListenableBuilder<ShareStickerValue?>(
              valueListenable: controller.liveStickerDraft,
              builder:
                  (_, __, ___) => ValueListenableBuilder<ShareBackgroundEdit?>(
                    valueListenable: controller.liveBackgroundTreatmentDraft,
                    builder:
                        (_, __, ___) =>
                            ValueListenableBuilder<ShareBackgroundConfig?>(
                              valueListenable: controller.liveBackgroundDraft,
                              builder: (_, __, ___) => _buildInspector(context),
                            ),
                  ),
            ),
      );

  Widget _buildInspector(BuildContext context) {
    final layer = controller.editingLayer;
    final selectedSticker = controller.editingLookSticker;
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF11192A),
        border: Border(left: BorderSide(color: Color(0xFF27324D))),
      ),
      child: ListView(
        key: const ValueKey('builder_inspector_scroll'),
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          _PaneTitle(
            title:
                selectedSticker != null
                    ? 'SELECTED STICKER'
                    : layer == null
                    ? 'INSPECTOR'
                    : 'SELECTED ${layer.type.toUpperCase()}',
          ),
          if (selectedSticker != null)
            _LookStickerFields(
              key: ValueKey(
                'look_sticker_fields_${selectedSticker.instanceId}',
              ),
              controller: controller,
              sticker: selectedSticker,
            )
          else if (layer?.type == 'background' &&
              controller.mode == ThemeBuilderMode.explore)
            _LookSection(controller: controller, onUploadPhoto: onUploadPhoto),
          if (selectedSticker == null && layer?.type == 'stickerWorkspace')
            _StickerWorkspaceSection(controller: controller),
          if (selectedSticker == null &&
              layer != null &&
              layer.type != 'background' &&
              layer.type != 'stickerWorkspace') ...[
            _LayerSection(
              key: ValueKey('layer_section_${layer.id}'),
              controller: controller,
              layer: layer,
            ),
            if (controller.mode == ThemeBuilderMode.explore)
              _StyleSection(
                key: ValueKey('style_section_${layer.id}'),
                controller: controller,
                layer: layer,
              ),
          ],
        ],
      ),
    );
  }
}

// Kept out of the focused inspector; schema migrations still use this editor.
// ignore: unused_element
final class _TemplateSection extends StatelessWidget {
  const _TemplateSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) {
    final template = controller.selectedTemplate;
    final runtime = template.runtimePermissions;
    return ExpansionTile(
      key: const ValueKey('builder_template_metadata'),
      initiallyExpanded: true,
      title: Text('Template: ${template.label}'),
      subtitle: Text(
        '${_humanize(template.family.name)} · ${_humanize(template.primaryJourneyState.name)}',
      ),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        _StringField(
          label: 'Template label',
          value: template.label,
          onChanged: (value) => controller.updateSelectedTemplate(label: value),
        ),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<ShareTemplateFamily>(
                value: template.family,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Family',
                  isDense: true,
                ),
                items: [
                  for (final value in ShareTemplateFamily.values)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        _humanize(value.name),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged:
                    (value) =>
                        value == null
                            ? null
                            : controller.updateSelectedTemplate(family: value),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<ShareJourneyState>(
                value: template.primaryJourneyState,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Journey state',
                  isDense: true,
                ),
                items: [
                  for (final value in ShareJourneyState.values)
                    DropdownMenuItem(
                      value: value,
                      child: Text(
                        _humanize(value.name),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged:
                    (value) =>
                        value == null
                            ? null
                            : controller.updateSelectedTemplate(
                              primaryJourneyState: value,
                            ),
              ),
            ),
          ],
        ),
        _StringField(
          label: 'Variant',
          value: template.variant,
          onChanged:
              (value) => controller.updateSelectedTemplate(variant: value),
        ),
        _StringField(
          label: 'Narrative intent',
          value: template.narrativeIntent,
          onChanged:
              (value) =>
                  controller.updateSelectedTemplate(narrativeIntent: value),
        ),
        DropdownButtonFormField<ShareSemanticRole>(
          value: template.primaryAnchor,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: 'Primary anchor',
            isDense: true,
          ),
          items: [
            for (final value in ShareSemanticRole.values)
              DropdownMenuItem(
                value: value,
                child: Text(
                  _humanize(value.name),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged:
              (value) =>
                  value == null
                      ? null
                      : controller.updateSelectedTemplate(primaryAnchor: value),
        ),
        _NumberField(
          label: 'Supported media count',
          value: template.supportedMediaCount.toDouble(),
          onChanged:
              (value) => controller.updateSelectedTemplate(
                supportedMediaCount: value.round().clamp(0, 8),
              ),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          title: const Text('Supports comparison'),
          value: template.supportsComparison,
          onChanged:
              (value) =>
                  controller.updateSelectedTemplate(supportsComparison: value),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          title: const Text('Supports proof'),
          value: template.supportsProof,
          onChanged:
              (value) =>
                  controller.updateSelectedTemplate(supportsProof: value),
        ),
        _RoleSelector(
          label: 'Required roles',
          values: template.requiredContentRoles,
          onChanged:
              (values) => controller.updateSelectedTemplate(
                requiredContentRoles: values,
                optionalContentRoles: template.optionalContentRoles.difference(
                  values,
                ),
              ),
        ),
        _RoleSelector(
          label: 'Optional roles',
          values: template.optionalContentRoles,
          onChanged:
              (values) => controller.updateSelectedTemplate(
                optionalContentRoles: values,
                requiredContentRoles: template.requiredContentRoles.difference(
                  values,
                ),
              ),
        ),
        const Align(
          alignment: Alignment.centerLeft,
          child: Padding(
            padding: EdgeInsets.only(top: 8, bottom: 4),
            child: Text(
              'RUNTIME PERMISSIONS',
              style: TextStyle(
                color: Colors.white54,
                fontSize: 10,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
        _PermissionSwitch(
          label: 'Replace media',
          value: runtime.userCanReplaceMedia,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanReplaceMedia: value,
                ),
              ),
        ),
        _PermissionSwitch(
          label: 'Crop media',
          value: runtime.userCanCropMedia,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(userCanCropMedia: value),
              ),
        ),
        _PermissionSwitch(
          label: 'Edit headline',
          value: runtime.userCanEditHeadline,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanEditHeadline: value,
                ),
              ),
        ),
        _PermissionSwitch(
          label: 'Edit proof value',
          value: runtime.userCanEditProofValue,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanEditProofValue: value,
                ),
              ),
        ),
        _PermissionSwitch(
          label: 'Choose alternate template',
          value: runtime.userCanChooseAlternateTemplate,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanChooseAlternateTemplate: value,
                ),
              ),
        ),
        _PermissionSwitch(
          label: 'Hide optional note',
          value: runtime.userCanHideOptionalNote,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanHideOptionalNote: value,
                ),
              ),
        ),
        _PermissionSwitch(
          label: 'Edit decorations',
          value: runtime.userCanEditDecorations,
          onChanged:
              (value) => controller.updateSelectedTemplate(
                runtimePermissions: runtime.copyWith(
                  userCanEditDecorations: value,
                ),
              ),
        ),
      ],
    );
  }
}

final class _RoleSelector extends StatelessWidget {
  const _RoleSelector({
    required this.label,
    required this.values,
    required this.onChanged,
  });

  final String label;
  final Set<ShareSemanticRole> values;
  final ValueChanged<Set<ShareSemanticRole>> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 10),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: Colors.white70, fontSize: 12),
        ),
        const SizedBox(height: 4),
        Wrap(
          spacing: 5,
          runSpacing: 3,
          children: [
            for (final role in ShareSemanticRole.values)
              if (role != ShareSemanticRole.unassigned)
                FilterChip(
                  label: Text(_humanize(role.name)),
                  selected: values.contains(role),
                  onSelected: (selected) {
                    final next = {...values};
                    selected ? next.add(role) : next.remove(role);
                    onChanged(next);
                  },
                ),
          ],
        ),
      ],
    ),
  );
}

final class _PermissionSwitch extends StatelessWidget {
  const _PermissionSwitch({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => SwitchListTile.adaptive(
    dense: true,
    contentPadding: EdgeInsets.zero,
    title: Text(label, style: const TextStyle(fontSize: 12)),
    value: value,
    onChanged: onChanged,
  );
}

// ignore: unused_element
final class _ValidationSection extends StatelessWidget {
  const _ValidationSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) {
    final result = PtwTemplateValidator.validate(
      controller.theme,
      controller.selectedTemplate,
    );
    return ExpansionTile(
      key: const ValueKey('builder_ptw_validation'),
      initiallyExpanded: true,
      leading: CircleAvatar(
        radius: 18,
        backgroundColor:
            result.isReady ? const Color(0xFF146C50) : const Color(0xFF8C2638),
        child: Text(
          '${result.score}',
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900),
        ),
      ),
      title: const Text('PTW validation'),
      subtitle: Text(
        result.isReady
            ? '${result.warningCount} warning(s) · export ready'
            : '${result.errorCount} blocking issue(s)',
      ),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        if (result.issues.isEmpty)
          const ListTile(
            dense: true,
            leading: Icon(Icons.check_circle_outline, color: Color(0xFF66E3A4)),
            title: Text('No issues found'),
          ),
        for (final issue in result.issues)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              switch (issue.severity) {
                PtwValidationSeverity.error => Icons.error_outline,
                PtwValidationSeverity.warning => Icons.warning_amber_rounded,
                PtwValidationSeverity.note => Icons.info_outline,
              },
              color: switch (issue.severity) {
                PtwValidationSeverity.error => const Color(0xFFFF5D73),
                PtwValidationSeverity.warning => const Color(0xFFFFD84A),
                PtwValidationSeverity.note => Colors.white54,
              },
            ),
            title: Text(issue.message, style: const TextStyle(fontSize: 12)),
            subtitle: Text(issue.code),
          ),
      ],
    );
  }
}

// ignore: unused_element
final class _ThemeSection extends StatelessWidget {
  const _ThemeSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    initiallyExpanded: false,
    title: const Text('Theme & canvas'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      _StringField(
        label: 'Theme name',
        value: controller.theme.name,
        onChanged: (value) => controller.updateMetadata(name: value),
      ),
      _StringField(
        label: 'Theme ID',
        value: controller.theme.id,
        onChanged: (value) => controller.updateMetadata(id: value),
      ),
      Row(
        children: [
          Expanded(
            child: _NumberField(
              label: 'Logical W',
              value: controller.theme.canvas.width,
              onChanged: (value) => controller.updateMetadata(width: value),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _NumberField(
              label: 'Logical H',
              value: controller.theme.canvas.height,
              onChanged: (value) => controller.updateMetadata(height: value),
            ),
          ),
        ],
      ),
      Row(
        children: [
          Expanded(
            child: _NumberField(
              label: 'PNG W',
              value: controller.theme.canvas.outputWidth.toDouble(),
              onChanged:
                  (value) =>
                      controller.updateMetadata(outputWidth: value.round()),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _NumberField(
              label: 'PNG H',
              value: controller.theme.canvas.outputHeight.toDouble(),
              onChanged:
                  (value) =>
                      controller.updateMetadata(outputHeight: value.round()),
            ),
          ),
        ],
      ),
      _NumberField(
        label: 'Maximum stickers',
        value: controller.theme.maximumStickerCount.toDouble(),
        onChanged:
            (value) =>
                controller.updateMetadata(maximumStickerCount: value.round()),
      ),
      _NumberField(
        label: 'Safe inset',
        value: controller.theme.canvas.safeInset,
        onChanged: (value) => controller.updateMetadata(safeInset: value),
      ),
      _NumberField(
        label: 'Post corner radius',
        value: controller.theme.canvas.cornerRadius,
        onChanged: (value) => controller.updateMetadata(cornerRadius: value),
      ),
      _IconPickerField(
        label: 'Premium icon',
        value: controller.theme.premiumIcon,
        onChanged: (value) => controller.updateMetadata(premiumIcon: value),
      ),
    ],
  );
}

final class _LookSection extends StatelessWidget {
  const _LookSection({required this.controller, required this.onUploadPhoto});

  final ThemeBuilderController controller;
  final VoidCallback onUploadPhoto;

  @override
  Widget build(BuildContext context) {
    final look = controller.selectedLook;
    final backgroundTreatment =
        controller.liveBackgroundTreatmentDraft.value ??
        look.backgroundTreatment;
    final background = controller.theme.background(
      look.backgroundId ?? controller.theme.defaultBackgroundId,
    );
    return ExpansionTile(
      initiallyExpanded: true,
      title: Text('Look: ${look.label}'),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        _VisualPickerField<String>(
          key: const ValueKey('builder_background_visual_picker'),
          label: 'Background',
          value: background.id,
          selectedLabel: background.label,
          selectedPreview: _ThemePreviewThumbnail(
            theme: controller.theme,
            lookId: look.id,
            backgroundId: background.id,
          ),
          options: [
            for (final item in controller.theme.backgrounds)
              _VisualPickerOption(
                value: item.id,
                label: item.label,
                subtitle: item.kind,
                preview: _ThemePreviewThumbnail(
                  theme: controller.theme,
                  lookId: look.id,
                  backgroundId: item.id,
                ),
              ),
          ],
          onChanged:
              (value) => controller.updateSelectedLook(backgroundId: value),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.tonalIcon(
            key: const ValueKey('builder_upload_photo_gallery'),
            onPressed: onUploadPhoto,
            icon: const Icon(Icons.add_photo_alternate_outlined),
            label: const Text('Upload photo to gallery'),
          ),
        ),
        const SizedBox(height: 8),
        _ImmediateSliderField(
          key: const ValueKey('builder_look_blur_slider'),
          label: 'Photo blur',
          value: backgroundTreatment.blur,
          minimum: 0,
          maximum: 30,
          divisions: 30,
          onChangeStart: (_) => controller.beginBackgroundTreatmentEdit(),
          onChanged:
              (value) => controller.previewBackgroundTreatment(
                backgroundTreatment.copyWith(blur: value),
              ),
          onChangeEnd: (_) => controller.finishBackgroundTreatmentEdit(),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: Text(
                '${background.kind} settings',
                style: const TextStyle(color: Colors.white60),
              ),
            ),
            PopupMenuButton<String>(
              tooltip: 'Add background',
              onSelected: controller.addBackground,
              itemBuilder:
                  (_) => const [
                    PopupMenuItem(value: 'solid', child: Text('Solid')),
                    PopupMenuItem(
                      value: 'linear',
                      child: Text('Linear gradient'),
                    ),
                    PopupMenuItem(
                      value: 'radial',
                      child: Text('Radial gradient'),
                    ),
                    PopupMenuItem(
                      value: 'sweep',
                      child: Text('Sweep gradient'),
                    ),
                    PopupMenuItem(value: 'image', child: Text('Image / cover')),
                  ],
              icon: const Icon(Icons.add_rounded),
            ),
          ],
        ),
        _BackgroundFields(
          key: ValueKey('background_fields_${background.id}'),
          controller: controller,
          background: background,
        ),
      ],
    );
  }
}

final class _StickerWorkspaceSection extends StatelessWidget {
  const _StickerWorkspaceSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) {
    final look = controller.selectedLook;
    final canAdd =
        look.defaultStickers.length < controller.theme.maximumStickerCount;
    return ExpansionTile(
      key: const ValueKey('builder_sticker_workspace_inspector'),
      initiallyExpanded: true,
      title: Text(
        'Stickers (${look.defaultStickers.length}/${controller.theme.maximumStickerCount})',
      ),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        const Align(
          alignment: Alignment.centerLeft,
          child: Text(
            'Add a sticker, then select it on the canvas to edit it.',
            style: TextStyle(color: Colors.white60, fontSize: 12),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 94,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: controller.theme.stickers.length,
            separatorBuilder: (_, __) => const SizedBox(width: 7),
            itemBuilder: (context, index) {
              final sticker = controller.theme.stickers[index];
              return _StickerAddTile(
                theme: controller.theme,
                sticker: sticker,
                enabled: canAdd,
                onTap: () => controller.addLookSticker(sticker.id),
              );
            },
          ),
        ),
        if (look.defaultStickers.isNotEmpty) const Divider(),
        for (final placed in look.defaultStickers)
          ListTile(
            key: ValueKey('builder_placed_sticker_${placed.instanceId}'),
            dense: true,
            selected: controller.selectedLookStickerId == placed.instanceId,
            contentPadding: EdgeInsets.zero,
            onTap: () => controller.selectLookSticker(placed.instanceId),
            leading: _AssetThumbnail(
              asset: controller.theme.asset(
                controller.theme.sticker(placed.stickerId).assetId,
              ),
              size: 42,
            ),
            title: Text(controller.theme.sticker(placed.stickerId).label),
            trailing: IconButton(
              tooltip: 'Remove sticker',
              onPressed: () => controller.removeLookSticker(placed.instanceId),
              icon: const Icon(Icons.close_rounded),
            ),
          ),
      ],
    );
  }
}

final class _LookStickerFields extends StatelessWidget {
  const _LookStickerFields({
    required this.controller,
    required this.sticker,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareStickerValue sticker;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(8),
      child: Column(
        children: [
          Row(
            children: [
              _AssetThumbnail(
                asset: controller.theme.asset(
                  controller.theme.sticker(sticker.stickerId).assetId,
                ),
                size: 42,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(controller.theme.sticker(sticker.stickerId).label),
              ),
              IconButton(
                tooltip: 'Remove from look',
                onPressed:
                    () => controller.removeLookSticker(sticker.instanceId),
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Center X',
                  value: sticker.centerX,
                  onChanged:
                      (value) => controller.updateLookSticker(
                        sticker.instanceId,
                        centerX: value,
                      ),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Center Y',
                  value: sticker.centerY,
                  onChanged:
                      (value) => controller.updateLookSticker(
                        sticker.instanceId,
                        centerY: value,
                      ),
                ),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Scale',
                  value: sticker.scale,
                  onChanged:
                      (value) => controller.updateLookSticker(
                        sticker.instanceId,
                        scale: value,
                      ),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Rotation',
                  value: sticker.rotation,
                  onChanged:
                      (value) => controller.updateLookSticker(
                        sticker.instanceId,
                        rotation: value,
                      ),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

final class _StickerAddTile extends StatelessWidget {
  const _StickerAddTile({
    required this.theme,
    required this.sticker,
    required this.enabled,
    required this.onTap,
  });

  final ShareThemeConfig theme;
  final ShareStickerConfig sticker;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: enabled ? 1 : 0.42,
    child: InkWell(
      key: ValueKey('builder_add_sticker_${sticker.id}'),
      borderRadius: BorderRadius.circular(10),
      onTap: enabled ? onTap : null,
      child: SizedBox(
        width: 70,
        child: Column(
          children: [
            _AssetThumbnail(
              key: ValueKey('builder_sticker_thumbnail_${sticker.id}'),
              asset: theme.asset(sticker.assetId),
              size: 60,
            ),
            const SizedBox(height: 3),
            Text(
              sticker.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 10),
            ),
          ],
        ),
      ),
    ),
  );
}

final class _BackgroundFields extends StatelessWidget {
  const _BackgroundFields({
    required this.controller,
    required this.background,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareBackgroundConfig background;

  @override
  Widget build(BuildContext context) {
    final liveBackground = controller.liveBackgroundDraft.value;
    final background =
        liveBackground?.id == this.background.id
            ? liveBackground!
            : this.background;
    final properties = background.properties;
    ShareBackgroundConfig withProperties(Map<String, Object?> value) =>
        ShareBackgroundConfig(
          id: background.id,
          label: background.label,
          kind: background.kind,
          properties: value,
          access: background.access,
        );
    void replaceProperties(Map<String, Object?> value) =>
        controller.updateBackground(withProperties(value));
    void update(String key, Object? value) =>
        replaceProperties({...properties, key: value});
    final imageSource =
        properties['assetId'] is String
            ? 'asset:${properties['assetId']}'
            : 'binding:${properties['binding'] ?? 'cover'}';
    final selectedImageAsset =
        properties['assetId'] is String
            ? controller.theme.asset(properties['assetId'] as String)
            : null;
    return Column(
      children: [
        _AccessEditor(
          label: 'Background access',
          value: background.access,
          onChanged:
              (value) => controller.updateBackground(
                ShareBackgroundConfig(
                  id: background.id,
                  label: background.label,
                  kind: background.kind,
                  properties: properties,
                  access: value,
                ),
              ),
        ),
        _StringField(
          label: 'Background label',
          value: background.label,
          onChanged:
              (value) => controller.updateBackground(
                ShareBackgroundConfig(
                  id: background.id,
                  label: value,
                  kind: background.kind,
                  properties: properties,
                  access: background.access,
                ),
              ),
        ),
        if (background.kind == 'solid')
          _ColorPickerField(
            label: 'Background color',
            value: '${properties['color'] ?? '#FF315CFF'}',
            onChanged: (value) => update('color', value),
          ),
        if ({'linear', 'radial', 'sweep'}.contains(background.kind)) ...[
          for (
            var index = 0;
            index < (properties['colors'] as List<dynamic>).length;
            index++
          )
            _ColorPickerField(
              label: 'Gradient color ${index + 1}',
              value: '${(properties['colors'] as List<dynamic>)[index]}',
              onChanged: (value) {
                final colors = List<Object?>.from(
                  properties['colors'] as List<dynamic>,
                );
                colors[index] = value;
                update('colors', colors);
              },
            ),
          _StringField(
            label: 'Stops, comma-separated',
            value: (properties['stops'] as List<dynamic>).join(', '),
            onChanged:
                (value) => update(
                  'stops',
                  value
                      .split(',')
                      .map((item) => double.parse(item.trim()))
                      .toList(),
                ),
          ),
          _NumberField(
            label: 'Opacity',
            value: _number(properties['opacity'], 1),
            onChanged: (value) => update('opacity', value.clamp(0, 1)),
          ),
          _NumberField(
            label: 'Rotation (radians)',
            value: _number(properties['rotation'], 0),
            onChanged: (value) => update('rotation', value),
          ),
          DropdownButtonFormField<String>(
            value: '${properties['tileMode'] ?? 'clamp'}',
            decoration: const InputDecoration(labelText: 'Tile mode'),
            items: const [
              DropdownMenuItem(value: 'clamp', child: Text('Clamp')),
              DropdownMenuItem(value: 'repeat', child: Text('Repeat')),
              DropdownMenuItem(value: 'mirror', child: Text('Mirror')),
              DropdownMenuItem(value: 'decal', child: Text('Decal')),
            ],
            onChanged: (value) => update('tileMode', value),
          ),
        ],
        if (background.kind == 'linear') ...[
          _StringField(
            label: 'Begin alignment',
            value: '${properties['begin'] ?? 'topLeft'}',
            onChanged: (value) => update('begin', value),
          ),
          _StringField(
            label: 'End alignment',
            value: '${properties['end'] ?? 'bottomRight'}',
            onChanged: (value) => update('end', value),
          ),
        ],
        if (background.kind == 'radial') ...[
          _StringField(
            label: 'Center alignment',
            value: '${properties['center'] ?? 'center'}',
            onChanged: (value) => update('center', value),
          ),
          _NumberField(
            label: 'Radius',
            value: _number(properties['radius'], 0.5),
            onChanged: (value) => update('radius', value),
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Focal X',
                  value: _number(properties['focalX'], 0),
                  onChanged: (value) => update('focalX', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Focal Y',
                  value: _number(properties['focalY'], 0),
                  onChanged: (value) => update('focalY', value),
                ),
              ),
            ],
          ),
          _NumberField(
            label: 'Focal radius',
            value: _number(properties['focalRadius'], 0),
            onChanged: (value) => update('focalRadius', value),
          ),
        ],
        if (background.kind == 'sweep') ...[
          _StringField(
            label: 'Center alignment',
            value: '${properties['center'] ?? 'center'}',
            onChanged: (value) => update('center', value),
          ),
          _NumberField(
            label: 'Start angle',
            value: _number(properties['startAngle'], 0),
            onChanged: (value) => update('startAngle', value),
          ),
          _NumberField(
            label: 'End angle',
            value: _number(properties['endAngle'], 6.283185307),
            onChanged: (value) => update('endAngle', value),
          ),
        ],
        if (background.kind == 'image') ...[
          _VisualPickerField<String>(
            key: const ValueKey('builder_background_image_visual_picker'),
            label: 'Background image source',
            value: imageSource,
            selectedLabel:
                selectedImageAsset?.id ??
                (properties['binding'] == 'avatar'
                    ? 'Sample avatar'
                    : 'Project cover'),
            selectedPreview:
                selectedImageAsset == null
                    ? _BoundImagePreview(
                      binding: '${properties['binding'] ?? 'cover'}',
                    )
                    : _AssetThumbnail(asset: selectedImageAsset, size: 54),
            options: [
              const _VisualPickerOption(
                value: 'binding:cover',
                label: 'Project cover',
                subtitle: 'Customer content',
                preview: _BoundImagePreview(binding: 'cover'),
              ),
              const _VisualPickerOption(
                value: 'binding:avatar',
                label: 'Customer avatar',
                subtitle: 'Customer content',
                preview: _BoundImagePreview(binding: 'avatar'),
              ),
              for (final asset in controller.theme.assets)
                if (asset.kind == 'image')
                  _VisualPickerOption(
                    value: 'asset:${asset.id}',
                    label: asset.id,
                    subtitle: 'Image asset',
                    preview: _AssetThumbnail(asset: asset, size: 96),
                  ),
            ],
            onChanged: (value) {
              final next =
                  <String, Object?>{...properties}
                    ..remove('binding')
                    ..remove('assetId');
              if (value.startsWith('asset:')) {
                next['assetId'] = value.substring(6);
              } else {
                next['binding'] = value.substring(8);
              }
              replaceProperties(next);
            },
          ),
          _ImmediateSliderField(
            key: const ValueKey('builder_background_blur_slider'),
            label: 'Blur',
            value: _number(properties['blur'], 0),
            minimum: 0,
            maximum: 30,
            divisions: 30,
            onChangeStart: (_) => controller.beginBackgroundEdit(),
            onChanged:
                (value) => controller.previewBackground(
                  withProperties({...properties, 'blur': value}),
                ),
            onChangeEnd: (_) => controller.finishBackgroundEdit(),
          ),
          _StringField(
            label: 'Fit',
            value: '${properties['fit'] ?? 'cover'}',
            onChanged: (value) => update('fit', value),
          ),
          _StringField(
            label: 'Alignment',
            value: '${properties['alignment'] ?? 'center'}',
            onChanged: (value) => update('alignment', value),
          ),
          _ImageAssetPickerField(
            key: const ValueKey('builder_background_fallback_visual_picker'),
            theme: controller.theme,
            label: 'Fallback image',
            assetId: properties['fallbackAssetId'] as String?,
            emptyLabel: 'No fallback image',
            onChanged: (value) => update('fallbackAssetId', value),
          ),
          _ColorPickerField(
            label: 'Overlay color',
            value: '${properties['overlayColor'] ?? '#00000000'}',
            onChanged: (value) => update('overlayColor', value),
          ),
        ],
      ],
    );
  }
}

final class _LayerSection extends StatelessWidget {
  const _LayerSection({
    required this.controller,
    required this.layer,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    initiallyExpanded: true,
    title: Text(layer.label),
    subtitle: const Text('Position, size and visibility'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: const Text('Visible'),
        value: layer.visible,
        onChanged: controller.updateSelectedVisibility,
      ),
      Row(
        children: [
          Expanded(
            child: _NumberField(
              label: 'X',
              value: layer.transform.x,
              onChanged:
                  (value) => controller.updateSelectedTransform(
                    layer.transform.copyWith(x: value),
                  ),
            ),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: _NumberField(
              label: 'Y',
              value: layer.transform.y,
              onChanged:
                  (value) => controller.updateSelectedTransform(
                    layer.transform.copyWith(y: value),
                  ),
            ),
          ),
        ],
      ),
      Row(
        children: [
          Expanded(
            child: _NumberField(
              label: 'Width',
              value: layer.transform.width,
              onChanged:
                  (value) => controller.updateSelectedTransform(
                    layer.transform.copyWith(width: value),
                  ),
            ),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: _NumberField(
              label: 'Height',
              value: layer.transform.height,
              onChanged:
                  (value) => controller.updateSelectedTransform(
                    layer.transform.copyWith(height: value),
                  ),
            ),
          ),
        ],
      ),
      _NumberField(
        label: 'Rotation (radians)',
        value: layer.transform.rotation,
        onChanged:
            (value) => controller.updateSelectedTransform(
              layer.transform.copyWith(rotation: value),
            ),
      ),
    ],
  );
}

final class _StyleSection extends StatelessWidget {
  const _StyleSection({
    required this.controller,
    required this.layer,
    super.key,
  });

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;

  @override
  Widget build(BuildContext context) {
    final style = layer.style;
    Widget liveColor(String label, String property, String fallback) =>
        _ColorPickerField(
          label: label,
          value: '${style[property] ?? fallback}',
          onChanged: (value) => controller.updateLayerStyle(property, value),
          onPreviewStart: controller.beginSelectedLayerStyleEdit,
          onPreviewChanged:
              (value) => controller.previewSelectedLayerStyle(property, value),
          onPreviewEnd: controller.finishSelectedLayerStyleEdit,
        );
    return ExpansionTile(
      initiallyExpanded: true,
      title: const Text('Appearance'),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        if (layer.type == 'text') ...[
          _VisualPickerField<String>(
            key: const ValueKey('builder_font_visual_picker'),
            label: 'Font family',
            value: '${style['fontFamily'] ?? 'PtwRoboto'}',
            selectedLabel: '${style['fontFamily'] ?? 'PtwRoboto'}',
            selectedPreview: _FontPreview(
              family: '${style['fontFamily'] ?? 'PtwRoboto'}',
            ),
            options: [
              for (final family in _fontFamilies(controller.theme))
                _VisualPickerOption(
                  value: family,
                  label: family,
                  preview: _FontPreview(family: family),
                ),
            ],
            onChanged:
                (value) => controller.updateLayerStyle('fontFamily', value),
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Font size',
                  value: _number(style['fontSize'], 30),
                  onChanged:
                      (value) => controller.updateLayerStyle('fontSize', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Weight',
                  value: _number(style['fontWeight'], 700),
                  onChanged:
                      (value) => controller.updateLayerStyle(
                        'fontWeight',
                        value.round(),
                      ),
                ),
              ),
            ],
          ),
          liveColor('Stroke color', 'strokeColor', '#FF000000'),
          liveColor('Text color', 'color', '#FFFFFFFF'),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Autosize text'),
            value: style['autoSize'] == true,
            onChanged:
                (value) => controller.updateLayerStyle('autoSize', value),
          ),
          if (style['autoSize'] == true)
            _NumberField(
              label: 'Minimum font size',
              value: _number(style['minFontSize'], 12),
              onChanged:
                  (value) => controller.updateLayerStyle('minFontSize', value),
            ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Italic'),
            value: style['italic'] == true,
            onChanged: (value) => controller.updateLayerStyle('italic', value),
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Line height',
                  value: _number(style['lineHeight'], 1),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('lineHeight', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Letter spacing',
                  value: _number(style['letterSpacing'], 0),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('letterSpacing', value),
                ),
              ),
            ],
          ),
          DropdownButtonFormField<String>(
            value: '${style['textAlign'] ?? 'center'}',
            decoration: const InputDecoration(labelText: 'Text alignment'),
            items: const [
              DropdownMenuItem(value: 'left', child: Text('Left')),
              DropdownMenuItem(value: 'center', child: Text('Center')),
              DropdownMenuItem(value: 'right', child: Text('Right')),
              DropdownMenuItem(value: 'justify', child: Text('Justify')),
            ],
            onChanged:
                (value) => controller.updateLayerStyle('textAlign', value),
          ),
          _StringField(
            label: 'Content alignment',
            value: '${style['alignment'] ?? 'center'}',
            onChanged:
                (value) => controller.updateLayerStyle('alignment', value),
          ),
          DropdownButtonFormField<String>(
            value: '${style['overflow'] ?? 'ellipsis'}',
            decoration: const InputDecoration(labelText: 'Overflow'),
            items: const [
              DropdownMenuItem(value: 'ellipsis', child: Text('Ellipsis')),
              DropdownMenuItem(value: 'clip', child: Text('Clip')),
              DropdownMenuItem(value: 'fade', child: Text('Fade')),
              DropdownMenuItem(value: 'visible', child: Text('Visible')),
            ],
            onChanged:
                (value) => controller.updateLayerStyle('overflow', value),
          ),
          liveColor('Text background color', 'backgroundColor', '#00000000'),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Stroke',
                  value: _number(style['strokeWidth'], 0),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('strokeWidth', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Max lines',
                  value: _number(style['maxLines'], 3),
                  onChanged:
                      (value) => controller.updateLayerStyle(
                        'maxLines',
                        value.round(),
                      ),
                ),
              ),
            ],
          ),
        ],
        if (layer.type == 'image' || layer.type == 'asset') ...[
          if (layer.binding == null || layer.binding!.isEmpty) ...[
            _ImageAssetPickerField(
              key: const ValueKey('builder_image_asset_visual_picker'),
              theme: controller.theme,
              label:
                  layer.type == 'asset'
                      ? 'Static image asset'
                      : 'Default image asset',
              assetId: style['assetId'] as String?,
              emptyLabel: 'No default image',
              onChanged:
                  (value) => controller.updateLayerStyle('assetId', value),
            ),
            _ImageAssetPickerField(
              key: const ValueKey('builder_fallback_asset_visual_picker'),
              theme: controller.theme,
              label: 'Fallback image',
              assetId: style['fallbackAssetId'] as String?,
              emptyLabel: 'No fallback image',
              onChanged:
                  (value) =>
                      controller.updateLayerStyle('fallbackAssetId', value),
            ),
          ],
          DropdownButtonFormField<String>(
            value: '${style['fit'] ?? 'cover'}',
            decoration: const InputDecoration(labelText: 'Image fit'),
            items: const [
              DropdownMenuItem(value: 'cover', child: Text('Cover')),
              DropdownMenuItem(value: 'contain', child: Text('Contain')),
              DropdownMenuItem(value: 'fill', child: Text('Fill')),
              DropdownMenuItem(value: 'fitWidth', child: Text('Fit width')),
              DropdownMenuItem(value: 'fitHeight', child: Text('Fit height')),
            ],
            onChanged: (value) => controller.updateLayerStyle('fit', value),
          ),
          DropdownButtonFormField<String>(
            value: '${style['imageAlignment'] ?? 'center'}',
            decoration: const InputDecoration(labelText: 'Photo position'),
            items: const [
              DropdownMenuItem(value: 'topLeft', child: Text('Top left')),
              DropdownMenuItem(value: 'topCenter', child: Text('Top center')),
              DropdownMenuItem(value: 'topRight', child: Text('Top right')),
              DropdownMenuItem(value: 'centerLeft', child: Text('Center left')),
              DropdownMenuItem(value: 'center', child: Text('Center')),
              DropdownMenuItem(
                value: 'centerRight',
                child: Text('Center right'),
              ),
              DropdownMenuItem(value: 'bottomLeft', child: Text('Bottom left')),
              DropdownMenuItem(
                value: 'bottomCenter',
                child: Text('Bottom center'),
              ),
              DropdownMenuItem(
                value: 'bottomRight',
                child: Text('Bottom right'),
              ),
            ],
            onChanged:
                (value) => controller.updateLayerStyle('imageAlignment', value),
          ),
          DropdownButtonFormField<String>(
            value: '${style['clip'] ?? 'rounded'}',
            decoration: const InputDecoration(labelText: 'Clip'),
            items: const [
              DropdownMenuItem(value: 'none', child: Text('None')),
              DropdownMenuItem(value: 'rounded', child: Text('Rounded')),
              DropdownMenuItem(value: 'oval', child: Text('Oval')),
            ],
            onChanged: (value) => controller.updateLayerStyle('clip', value),
          ),
          _ImmediateSliderField(
            label: 'Opacity',
            value: _number(style['opacity'], 1),
            minimum: 0,
            maximum: 1,
            divisions: 20,
            onChangeStart: (_) => controller.beginSelectedLayerStyleEdit(),
            onChanged:
                (value) =>
                    controller.previewSelectedLayerStyle('opacity', value),
            onChangeEnd: (_) => controller.finishSelectedLayerStyleEdit(),
          ),
          _ImmediateSliderField(
            key: const ValueKey('builder_layer_blur_slider'),
            label: 'Blur',
            value: _number(style['blur'], 0),
            minimum: 0,
            maximum: 30,
            divisions: 30,
            onChangeStart: (_) => controller.beginSelectedLayerStyleEdit(),
            onChanged:
                (value) => controller.previewSelectedLayerStyle('blur', value),
            onChangeEnd: (_) => controller.finishSelectedLayerStyleEdit(),
          ),
        ],
        if (layer.type == 'shape') ...[
          DropdownButtonFormField<String>(
            value: '${style['shape'] ?? 'rectangle'}',
            decoration: const InputDecoration(labelText: 'Shape'),
            items: const [
              DropdownMenuItem(value: 'rectangle', child: Text('Rectangle')),
              DropdownMenuItem(value: 'oval', child: Text('Oval')),
            ],
            onChanged: (value) => controller.updateLayerStyle('shape', value),
          ),
          liveColor('Fill color', 'color', '#FFFFFFFF'),
        ],
        if (layer.type != 'background' && layer.type != 'stickerWorkspace') ...[
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Border width',
                  value: _number(style['borderWidth'], 0),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('borderWidth', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Radius',
                  value: _number(style['borderRadius'], 0),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('borderRadius', value),
                ),
              ),
            ],
          ),
          liveColor('Border color', 'borderColor', '#FFFFFFFF'),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Shadow blur',
                  value: _number(style['shadowBlur'], 0),
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('shadowBlur', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Shadow X',
                  value: _number(style['shadowX'], 0),
                  onChanged:
                      (value) => controller.updateLayerStyle('shadowX', value),
                ),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Shadow Y',
                  value: _number(style['shadowY'], 0),
                  onChanged:
                      (value) => controller.updateLayerStyle('shadowY', value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: liveColor('Shadow color', 'shadowColor', '#88000000'),
              ),
            ],
          ),
        ],
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: () => _editStyleJson(context),
            icon: const Icon(Icons.data_object_rounded),
            label: const Text('Advanced style JSON'),
          ),
        ),
      ],
    );
  }

  Future<void> _editStyleJson(BuildContext context) async {
    final text = TextEditingController(
      text: const JsonEncoder.withIndent('  ').convert(layer.style),
    );
    final result = await showDialog<String>(
      context: context,
      builder:
          (dialogContext) => AlertDialog(
            title: const Text('Advanced style JSON'),
            content: SizedBox(
              width: 560,
              child: TextField(
                controller: text,
                minLines: 16,
                maxLines: 24,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext, text.text),
                child: const Text('Apply'),
              ),
            ],
          ),
    );
    text.dispose();
    if (result == null) return;
    final decoded = jsonDecode(result);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Style JSON must be an object');
    }
    controller.replaceLayerStyle(decoded);
  }
}

// ignore: unused_element
final class _AccessSection extends StatelessWidget {
  const _AccessSection({required this.controller, required this.layer});

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: const Text('User controls & premium'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      _AccessEditor(
        label: 'Layer visibility',
        value: layer.access,
        onChanged: controller.updateLayerAccess,
      ),
      for (final control in layer.controls)
        _BuilderControlEditor(controller: controller, control: control),
    ],
  );
}

final class _BuilderControlEditor extends StatelessWidget {
  const _BuilderControlEditor({
    required this.controller,
    required this.control,
  });

  final ThemeBuilderController controller;
  final ShareControlConfig control;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '${control.label} · ${control.kind.name}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 7),
          Row(
            children: [
              Expanded(
                child: _StringField(
                  label: 'Control label',
                  value: control.label,
                  onChanged:
                      (value) =>
                          controller.updateControl(control.id, label: value),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _StringField(
                  label: 'Capability',
                  value: control.capability,
                  onChanged:
                      (value) => controller.updateControl(
                        control.id,
                        capability: value,
                      ),
                ),
              ),
            ],
          ),
          if (control.kind == ShareControlKind.number) ...[
            Row(
              children: [
                Expanded(
                  child: _NumberField(
                    label: 'Minimum',
                    value: control.minimum ?? 0,
                    onChanged:
                        (value) => controller.updateControl(
                          control.id,
                          minimum: value,
                        ),
                  ),
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: _NumberField(
                    label: 'Maximum',
                    value: control.maximum ?? 100,
                    onChanged:
                        (value) => controller.updateControl(
                          control.id,
                          maximum: value,
                        ),
                  ),
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: _NumberField(
                    label: 'Default',
                    value:
                        control.defaultValue is num
                            ? (control.defaultValue! as num).toDouble()
                            : control.minimum ?? 0,
                    onChanged:
                        (value) => controller.updateControl(
                          control.id,
                          defaultValue: value,
                        ),
                  ),
                ),
              ],
            ),
          ],
          if (control.kind == ShareControlKind.choice) ...[
            _StringField(
              label: 'Allowed values, comma-separated',
              value: control.options.join(', '),
              onChanged:
                  (value) => controller.updateControl(
                    control.id,
                    options:
                        value
                            .split(',')
                            .map((item) => item.trim())
                            .where((item) => item.isNotEmpty)
                            .toList(),
                  ),
            ),
            _StringField(
              label: 'Default value',
              value: '${control.defaultValue ?? ''}',
              onChanged:
                  (value) =>
                      controller.updateControl(control.id, defaultValue: value),
            ),
          ],
          _AccessEditor(
            label: 'Access policy',
            value: control.access,
            onChanged:
                (value) => controller.updateControl(control.id, access: value),
          ),
        ],
      ),
    ),
  );
}

// ignore: unused_element
final class _ToolbarSection extends StatelessWidget {
  const _ToolbarSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: const Text('Customer toolbar'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      _VisualPickerField<String>(
        key: const ValueKey('builder_default_toolbar_visual_picker'),
        label: 'Default tab',
        value: controller.theme.defaultToolbarGroupId,
        selectedLabel:
            controller.theme.toolbar
                .firstWhere(
                  (item) => item.id == controller.theme.defaultToolbarGroupId,
                )
                .label,
        selectedPreview: _IconPreview(
          value:
              controller.theme.toolbar
                  .firstWhere(
                    (item) => item.id == controller.theme.defaultToolbarGroupId,
                  )
                  .icon,
        ),
        options: [
          for (final item in controller.theme.toolbar)
            _VisualPickerOption(
              value: item.id,
              label: item.label,
              subtitle: item.id,
              preview: _IconPreview(value: item.icon),
            ),
        ],
        onChanged: controller.setDefaultToolbarGroup,
      ),
      const SizedBox(height: 10),
      for (final item in controller.theme.toolbar)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              children: [
                _StringField(
                  label: 'Tab label (${item.id})',
                  value: item.label,
                  onChanged:
                      (value) =>
                          controller.updateToolbar(item.id, label: value),
                ),
                Row(
                  children: [
                    Expanded(
                      child: _IconPickerField(
                        label: 'Icon',
                        value: item.icon,
                        onChanged:
                            (value) =>
                                controller.updateToolbar(item.id, icon: value),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: _NumberField(
                        label: 'Order',
                        value: item.order.toDouble(),
                        onChanged:
                            (value) => controller.updateToolbar(
                              item.id,
                              order: value.round(),
                            ),
                      ),
                    ),
                  ],
                ),
                _AccessEditor(
                  label: 'Access',
                  value: item.access,
                  onChanged:
                      (value) => controller.updateToolbarAccess(item.id, value),
                ),
              ],
            ),
          ),
        ),
    ],
  );
}

// ignore: unused_element
final class _StickerCatalogSection extends StatelessWidget {
  const _StickerCatalogSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: Text('Sticker catalog (${controller.theme.stickers.length})'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    trailing: PopupMenuButton<String>(
      tooltip: 'Create sticker from image asset',
      onSelected: controller.addStickerConfig,
      itemBuilder:
          (_) => [
            for (final asset in controller.theme.assets)
              if (asset.kind == 'image' &&
                  !controller.theme.stickers.any(
                    (sticker) => sticker.assetId == asset.id,
                  ))
                PopupMenuItem(value: asset.id, child: Text(asset.id)),
          ],
      icon: const Icon(Icons.add_reaction_outlined),
    ),
    children: [
      for (final sticker in controller.theme.stickers)
        Card(
          key: ValueKey('builder_sticker_card_${sticker.id}'),
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              children: [
                Row(
                  children: [
                    _AssetThumbnail(
                      key: ValueKey('builder_sticker_thumbnail_${sticker.id}'),
                      asset: controller.theme.asset(sticker.assetId),
                      size: 72,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            sticker.id,
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            sticker.assetId,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white54,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Delete sticker definition',
                      onPressed:
                          () => controller.removeStickerConfig(sticker.id),
                      icon: const Icon(Icons.delete_outline_rounded),
                    ),
                  ],
                ),
                Row(
                  children: [
                    Expanded(
                      child: _StringField(
                        label: 'Label',
                        value: sticker.label,
                        onChanged:
                            (value) => controller.updateStickerConfig(
                              sticker.copyWith(label: value),
                            ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: _StringField(
                        label: 'Category',
                        value: sticker.category,
                        onChanged:
                            (value) => controller.updateStickerConfig(
                              sticker.copyWith(category: value),
                            ),
                      ),
                    ),
                  ],
                ),
                Row(
                  children: [
                    Expanded(
                      child: _NumberField(
                        label: 'Minimum scale',
                        value: sticker.minimumScale,
                        onChanged:
                            (value) => controller.updateStickerConfig(
                              sticker.copyWith(minimumScale: value),
                            ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: _NumberField(
                        label: 'Default scale',
                        value: sticker.defaultScale,
                        onChanged:
                            (value) => controller.updateStickerConfig(
                              sticker.copyWith(defaultScale: value),
                            ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: _NumberField(
                        label: 'Maximum scale',
                        value: sticker.maximumScale,
                        onChanged:
                            (value) => controller.updateStickerConfig(
                              sticker.copyWith(maximumScale: value),
                            ),
                      ),
                    ),
                  ],
                ),
                Wrap(
                  spacing: 4,
                  runSpacing: 0,
                  children: [
                    _StickerPermission(
                      label: 'Move',
                      value: sticker.canMove,
                      onChanged:
                          (value) => controller.updateStickerConfig(
                            sticker.copyWith(canMove: value),
                          ),
                    ),
                    _StickerPermission(
                      label: 'Resize',
                      value: sticker.canResize,
                      onChanged:
                          (value) => controller.updateStickerConfig(
                            sticker.copyWith(canResize: value),
                          ),
                    ),
                    _StickerPermission(
                      label: 'Rotate',
                      value: sticker.canRotate,
                      onChanged:
                          (value) => controller.updateStickerConfig(
                            sticker.copyWith(canRotate: value),
                          ),
                    ),
                    _StickerPermission(
                      label: 'Delete',
                      value: sticker.canDelete,
                      onChanged:
                          (value) => controller.updateStickerConfig(
                            sticker.copyWith(canDelete: value),
                          ),
                    ),
                  ],
                ),
                _AccessEditor(
                  label: 'Sticker access',
                  value: sticker.access,
                  onChanged:
                      (value) => controller.updateStickerConfig(
                        sticker.copyWith(access: value),
                      ),
                ),
              ],
            ),
          ),
        ),
    ],
  );
}

final class _StickerPermission extends StatelessWidget {
  const _StickerPermission({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 150,
    child: CheckboxListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      value: value,
      onChanged: (next) => onChanged(next ?? false),
    ),
  );
}

// ignore: unused_element
final class _AssetsSection extends StatelessWidget {
  const _AssetsSection({required this.controller, required this.onUploadPhoto});

  final ThemeBuilderController controller;
  final VoidCallback onUploadPhoto;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: Text('Assets (${controller.theme.assets.length})'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      Align(
        alignment: Alignment.centerLeft,
        child: FilledButton.tonalIcon(
          key: const ValueKey('builder_assets_upload_photo'),
          onPressed: onUploadPhoto,
          icon: const Icon(Icons.photo_library_outlined),
          label: const Text('Upload photo to gallery'),
        ),
      ),
      const SizedBox(height: 8),
      for (final asset in controller.theme.assets)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading:
              asset.kind == 'image'
                  ? _AssetThumbnail(asset: asset, size: 42)
                  : const Icon(Icons.font_download_outlined),
          title: Text(asset.id),
          subtitle: Text(asset.mimeType),
          trailing:
              asset.data == null
                  ? const Text('bundled')
                  : const Text('embedded'),
        ),
    ],
  );
}

// ignore: unused_element
final class _StickerMenuItem extends StatelessWidget {
  const _StickerMenuItem({required this.theme, required this.sticker});

  final ShareThemeConfig theme;
  final ShareStickerConfig sticker;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      _AssetThumbnail(asset: theme.asset(sticker.assetId), size: 38),
      const SizedBox(width: 10),
      Flexible(child: Text(sticker.label)),
    ],
  );
}

final class _AssetThumbnail extends StatelessWidget {
  const _AssetThumbnail({required this.asset, required this.size, super.key});

  final ShareAssetConfig asset;
  final double size;

  @override
  Widget build(BuildContext context) {
    final bytes = asset.embeddedBytes;
    final value =
        bytes != null
            ? ShareImageValue.memory(bytes, mimeType: asset.mimeType)
            : asset.path == null
            ? null
            : ShareImageValue.asset(asset.path!);
    final provider = value == null ? null : defaultShareImageResolver(value);
    return Container(
      width: size,
      height: size,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Colors.white10,
        border: Border.all(color: Colors.white24),
        borderRadius: BorderRadius.circular(9),
      ),
      child:
          provider == null
              ? const Icon(Icons.broken_image_outlined, color: Colors.white38)
              : Image(
                image: provider,
                fit: BoxFit.contain,
                errorBuilder:
                    (_, __, ___) => const Icon(
                      Icons.broken_image_outlined,
                      color: Colors.white38,
                    ),
              ),
    );
  }
}

final class _AccessEditor extends StatefulWidget {
  const _AccessEditor({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final ShareAccessPolicy value;
  final ValueChanged<ShareAccessPolicy> onChanged;

  @override
  State<_AccessEditor> createState() => _AccessEditorState();
}

final class _AccessEditorState extends State<_AccessEditor> {
  late String _key;

  @override
  void initState() {
    super.initState();
    _key = widget.value.entitlementKey ?? 'premium';
  }

  @override
  void didUpdateWidget(_AccessEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value.entitlementKey != widget.value.entitlementKey &&
        widget.value.entitlementKey != null) {
      _key = widget.value.entitlementKey!;
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          widget.label,
          style: const TextStyle(fontSize: 11, color: Colors.white60),
        ),
        const SizedBox(height: 3),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<ShareAccessMode>(
                value: widget.value.mode,
                isDense: true,
                items: const [
                  DropdownMenuItem(
                    value: ShareAccessMode.free,
                    child: Text('Free'),
                  ),
                  DropdownMenuItem(
                    value: ShareAccessMode.premiumVisible,
                    child: Text('Premium + badge'),
                  ),
                  DropdownMenuItem(
                    value: ShareAccessMode.premiumHidden,
                    child: Text('Premium hidden'),
                  ),
                ],
                onChanged:
                    (mode) => widget.onChanged(
                      ShareAccessPolicy(
                        mode: mode ?? ShareAccessMode.free,
                        entitlementKey:
                            mode == ShareAccessMode.free ? null : _key.trim(),
                      ),
                    ),
              ),
            ),
            if (widget.value.mode != ShareAccessMode.free) ...[
              const SizedBox(width: 7),
              SizedBox(
                width: 120,
                child: _StringField(
                  label: 'Entitlement',
                  value: _key,
                  onChanged: (value) {
                    _key = value.trim();
                    widget.onChanged(
                      ShareAccessPolicy(
                        mode: widget.value.mode,
                        entitlementKey: _key,
                      ),
                    );
                  },
                ),
              ),
            ],
          ],
        ),
      ],
    ),
  );
}

final class _StringField extends StatefulWidget {
  const _StringField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  State<_StringField> createState() => _StringFieldState();
}

final class _StringFieldState extends State<_StringField> {
  late final TextEditingController _text;
  late final FocusNode _focus;
  String? _error;

  @override
  void initState() {
    super.initState();
    _text = TextEditingController(text: widget.value);
    _focus = FocusNode()..addListener(_handleFocusChange);
  }

  @override
  void didUpdateWidget(_StringField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_focus.hasFocus && widget.value != _text.text) {
      _text.value = TextEditingValue(
        text: widget.value,
        selection: TextSelection.collapsed(offset: widget.value.length),
      );
      _error = null;
    }
  }

  @override
  void dispose() {
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _commit(String value) {
    String? error;
    try {
      widget.onChanged(value);
    } on Object catch (exception) {
      error = '$exception';
    }
    if (mounted && error != _error) setState(() => _error = error);
  }

  void _handleFocusChange() {
    if (_focus.hasFocus) return;
    if (widget.value != _text.text) {
      _text.value = TextEditingValue(
        text: widget.value,
        selection: TextSelection.collapsed(offset: widget.value.length),
      );
    }
    if (mounted && _error != null) setState(() => _error = null);
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextFormField(
      key: ValueKey('builder_string_field_${widget.label}'),
      controller: _text,
      focusNode: _focus,
      decoration: InputDecoration(
        labelText: widget.label,
        isDense: true,
        errorText: _error,
      ),
      onChanged: _commit,
      onFieldSubmitted: (_) => _focus.unfocus(),
    ),
  );
}

final class _NumberField extends StatefulWidget {
  const _NumberField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final double value;
  final ValueChanged<double> onChanged;

  @override
  State<_NumberField> createState() => _NumberFieldState();
}

final class _NumberFieldState extends State<_NumberField> {
  late final TextEditingController _text;
  late final FocusNode _focus;
  String? _error;

  String _formatted(double value) =>
      value.toStringAsFixed(value == value.roundToDouble() ? 0 : 3);

  @override
  void initState() {
    super.initState();
    _text = TextEditingController(text: _formatted(widget.value));
    _focus = FocusNode()..addListener(_handleFocusChange);
  }

  @override
  void didUpdateWidget(_NumberField oldWidget) {
    super.didUpdateWidget(oldWidget);
    final value = _formatted(widget.value);
    if (!_focus.hasFocus && value != _text.text) {
      _text.value = TextEditingValue(
        text: value,
        selection: TextSelection.collapsed(offset: value.length),
      );
      _error = null;
    }
  }

  @override
  void dispose() {
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _commit(String raw) {
    String? error;
    final parsed = double.tryParse(raw);
    if (parsed == null || !parsed.isFinite) {
      error = 'Enter a valid number';
    } else {
      try {
        widget.onChanged(parsed);
      } on Object catch (exception) {
        error = '$exception';
      }
    }
    if (mounted && error != _error) setState(() => _error = error);
  }

  void _handleFocusChange() {
    if (_focus.hasFocus) return;
    final value = _formatted(widget.value);
    if (value != _text.text) {
      _text.value = TextEditingValue(
        text: value,
        selection: TextSelection.collapsed(offset: value.length),
      );
    }
    if (mounted && _error != null) setState(() => _error = null);
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextFormField(
      key: ValueKey('builder_number_field_${widget.label}'),
      controller: _text,
      focusNode: _focus,
      keyboardType: const TextInputType.numberWithOptions(
        decimal: true,
        signed: true,
      ),
      decoration: InputDecoration(
        labelText: widget.label,
        isDense: true,
        errorText: _error,
      ),
      onChanged: _commit,
      onFieldSubmitted: (_) => _focus.unfocus(),
    ),
  );
}

final class _ImmediateSliderField extends StatelessWidget {
  const _ImmediateSliderField({
    required this.label,
    required this.value,
    required this.minimum,
    required this.maximum,
    required this.onChanged,
    this.onChangeStart,
    this.onChangeEnd,
    this.divisions,
    super.key,
  });

  final String label;
  final double value;
  final double minimum;
  final double maximum;
  final int? divisions;
  final ValueChanged<double> onChanged;
  final ValueChanged<double>? onChangeStart;
  final ValueChanged<double>? onChangeEnd;

  @override
  Widget build(BuildContext context) {
    final safeValue = value.clamp(minimum, maximum);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ),
              Text(
                safeValue.toStringAsFixed(
                  safeValue == safeValue.roundToDouble() ? 0 : 1,
                ),
                style: const TextStyle(color: Colors.white54, fontSize: 11),
              ),
            ],
          ),
          Slider(
            value: safeValue,
            min: minimum,
            max: maximum,
            divisions: divisions,
            label: safeValue.toStringAsFixed(1),
            onChangeStart: onChangeStart,
            onChanged: onChanged,
            onChangeEnd: onChangeEnd,
          ),
        ],
      ),
    );
  }
}

const _builderPresetColors = <String>[
  '#FFFFFFFF',
  '#FF111827',
  '#FFF4066E',
  '#FFFFE557',
  '#FF315CFF',
  '#FF4038B8',
  '#FF00A39A',
  '#FFBFF7FF',
  '#FFFFB38A',
  '#00000000',
];

final class _ColorPickerField extends StatelessWidget {
  const _ColorPickerField({
    required this.label,
    required this.value,
    required this.onChanged,
    this.onPreviewStart,
    this.onPreviewChanged,
    this.onPreviewEnd,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;
  final VoidCallback? onPreviewStart;
  final ValueChanged<String>? onPreviewChanged;
  final VoidCallback? onPreviewEnd;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ),
            Text(
              value.toUpperCase(),
              style: const TextStyle(color: Colors.white54, fontSize: 10),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final preset in _builderPresetColors)
              Tooltip(
                message: preset,
                child: InkWell(
                  key: ValueKey('builder_color_preset_${label}_$preset'),
                  customBorder: const CircleBorder(),
                  onTap: () => onChanged(preset),
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: _parseBuilderColor(preset),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color:
                            preset.toUpperCase() == value.toUpperCase()
                                ? const Color(0xFFFFE557)
                                : Colors.white38,
                        width:
                            preset.toUpperCase() == value.toUpperCase() ? 3 : 1,
                      ),
                    ),
                  ),
                ),
              ),
            OutlinedButton.icon(
              key: ValueKey('builder_color_custom_$label'),
              onPressed:
                  () => showDialog<void>(
                    context: context,
                    builder:
                        (_) => _BuilderColorDialog(
                          label: label,
                          value: value,
                          onChanged: onChanged,
                          onPreviewStart: onPreviewStart,
                          onPreviewChanged: onPreviewChanged,
                          onPreviewEnd: onPreviewEnd,
                        ),
                  ),
              icon: const Icon(Icons.tune_rounded, size: 17),
              label: const Text('Custom'),
            ),
          ],
        ),
      ],
    ),
  );
}

final class _BuilderColorDialog extends StatefulWidget {
  const _BuilderColorDialog({
    required this.label,
    required this.value,
    required this.onChanged,
    this.onPreviewStart,
    this.onPreviewChanged,
    this.onPreviewEnd,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;
  final VoidCallback? onPreviewStart;
  final ValueChanged<String>? onPreviewChanged;
  final VoidCallback? onPreviewEnd;

  @override
  State<_BuilderColorDialog> createState() => _BuilderColorDialogState();
}

final class _BuilderColorDialogState extends State<_BuilderColorDialog> {
  late HSVColor _color;

  @override
  void initState() {
    super.initState();
    _color = HSVColor.fromColor(_parseBuilderColor(widget.value));
  }

  void _update(HSVColor value) {
    setState(() => _color = value);
    (widget.onPreviewChanged ?? widget.onChanged)(
      _builderColorHex(value.toColor()),
    );
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('Custom ${widget.label.toLowerCase()}'),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              height: 72,
              decoration: BoxDecoration(
                color: _color.toColor(),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: Colors.white38),
              ),
              alignment: Alignment.center,
              child: Text(
                _builderColorHex(_color.toColor()),
                style: TextStyle(
                  color: _color.value > 0.55 ? Colors.black : Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            _ColorSliderRow(
              label: 'Hue',
              value: _color.hue,
              maximum: 360,
              onChangeStart: widget.onPreviewStart,
              onChanged: (value) => _update(_color.withHue(value)),
              onChangeEnd: widget.onPreviewEnd,
            ),
            _ColorSliderRow(
              label: 'Saturation',
              value: _color.saturation,
              maximum: 1,
              onChangeStart: widget.onPreviewStart,
              onChanged: (value) => _update(_color.withSaturation(value)),
              onChangeEnd: widget.onPreviewEnd,
            ),
            _ColorSliderRow(
              label: 'Brightness',
              value: _color.value,
              maximum: 1,
              onChangeStart: widget.onPreviewStart,
              onChanged: (value) => _update(_color.withValue(value)),
              onChangeEnd: widget.onPreviewEnd,
            ),
            _ColorSliderRow(
              label: 'Opacity',
              value: _color.alpha,
              maximum: 1,
              onChangeStart: widget.onPreviewStart,
              onChanged: (value) => _update(_color.withAlpha(value)),
              onChangeEnd: widget.onPreviewEnd,
            ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Done'),
      ),
    ],
  );
}

final class _ColorSliderRow extends StatelessWidget {
  const _ColorSliderRow({
    required this.label,
    required this.value,
    required this.maximum,
    required this.onChanged,
    this.onChangeStart,
    this.onChangeEnd,
  });

  final String label;
  final double value;
  final double maximum;
  final ValueChanged<double> onChanged;
  final VoidCallback? onChangeStart;
  final VoidCallback? onChangeEnd;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      SizedBox(width: 78, child: Text(label)),
      Expanded(
        child: Slider(
          value: value.clamp(0, maximum),
          min: 0,
          max: maximum,
          onChangeStart: onChangeStart == null ? null : (_) => onChangeStart!(),
          onChanged: onChanged,
          onChangeEnd: onChangeEnd == null ? null : (_) => onChangeEnd!(),
        ),
      ),
      SizedBox(
        width: 46,
        child: Text(
          maximum == 360 ? '${value.round()}°' : '${(value * 100).round()}%',
          textAlign: TextAlign.end,
        ),
      ),
    ],
  );
}

final class _PaneTitle extends StatelessWidget {
  const _PaneTitle({required this.title, this.trailing});

  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 42,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 7, 2),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: Colors.white54,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
              ),
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    ),
  );
}

IconData _layerIcon(String type) => switch (type) {
  'text' => Icons.text_fields_rounded,
  'image' => Icons.photo_outlined,
  'asset' => Icons.branding_watermark_outlined,
  'shape' => Icons.category_outlined,
  'background' => Icons.wallpaper_rounded,
  'stickerWorkspace' => Icons.emoji_emotions_outlined,
  _ => Icons.extension_outlined,
};

IconData _namedBuilderIcon(String value) => switch (value) {
  'templates' => Icons.dashboard_customize_outlined,
  'palette' => Icons.palette_outlined,
  'image' => Icons.photo_outlined,
  'sticker' => Icons.emoji_emotions_outlined,
  'tune' => Icons.tune_rounded,
  'magic' => Icons.auto_awesome_outlined,
  'workspace_premium' => Icons.workspace_premium,
  'lock' => Icons.lock_rounded,
  'diamond' => Icons.diamond_outlined,
  'star' => Icons.star_rounded,
  _ => Icons.text_fields_rounded,
};

double _number(Object? value, double fallback) =>
    value is num ? value.toDouble() : fallback;

String _humanize(String value) {
  final spaced = value.replaceAllMapped(
    RegExp(r'([a-z0-9])([A-Z])'),
    (match) => '${match.group(1)} ${match.group(2)}',
  );
  return '${spaced[0].toUpperCase()}${spaced.substring(1)}';
}

Color _parseBuilderColor(String value) =>
    shareColor(value, fallback: const Color(0xFFFFFFFF));

String _builderColorHex(Color value) =>
    '#${value.toARGB32().toRadixString(16).padLeft(8, '0').toUpperCase()}';
