import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../generated_share_editor/generated_share_editor.dart';
import 'share_theme_builder_web_io.dart';
import 'theme_builder_controller.dart';
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
        theme = ShareThemeBundle.fromJsonString(saved);
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
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder:
        (context, _) => Scaffold(
          body: SafeArea(
            child: Column(
              children: [
                _BuilderHeader(
                  controller: widget.controller,
                  busy: _busy,
                  onImport: _importJson,
                  onExport: _exportJson,
                  onGenerate: _generateZip,
                  onImportAsset: _importAsset,
                  onImportFont: _importFont,
                ),
                Expanded(
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final workspace = SizedBox(
                        width:
                            constraints.maxWidth < 1080
                                ? 1080
                                : constraints.maxWidth,
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            SizedBox(
                              width: 270,
                              child: _LayersPane(controller: widget.controller),
                            ),
                            Expanded(
                              child: _DesignCanvas(
                                controller: widget.controller,
                              ),
                            ),
                            SizedBox(
                              width: 360,
                              child: _InspectorPane(
                                controller: widget.controller,
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
    await widget.controller.addAsset(
      fileName: file.name,
      mimeType: file.mimeType,
      bytes: file.bytes,
      kind: 'image',
    );
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
    child: Row(
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
        const SizedBox(width: 11),
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
        const SizedBox(width: 22),
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
        const Spacer(),
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
        const SizedBox(width: 12),
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
        const SizedBox(width: 8),
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
        _PaneTitle(
          title: 'LOOKS',
          trailing: IconButton(
            tooltip: 'Add look',
            onPressed: controller.addLook,
            icon: const Icon(Icons.add_rounded, size: 19),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: controller.selectedLookId,
                  isExpanded: true,
                  decoration: const InputDecoration(isDense: true),
                  items: [
                    for (final look in controller.theme.looks)
                      DropdownMenuItem(value: look.id, child: Text(look.label)),
                  ],
                  onChanged: (value) {
                    if (value != null) controller.selectLook(value);
                  },
                ),
              ),
              IconButton(
                tooltip: 'Delete look',
                onPressed:
                    controller.theme.looks.length > 1
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
          onChanged: controller.toggleLookOverrides,
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
            itemCount: controller.theme.layers.length,
            onReorder: (oldIndex, newIndex) {
              final adjusted = newIndex > oldIndex ? newIndex - 1 : newIndex;
              controller.selectLayer(controller.theme.layers[oldIndex].id);
              controller.moveSelectedLayer(adjusted - oldIndex);
            },
            itemBuilder: (context, index) {
              final layer = controller.theme.layers[index];
              final selected = controller.selectedLayerId == layer.id;
              return Card(
                key: ValueKey(layer.id),
                color:
                    selected
                        ? const Color(0xFF2C385A)
                        : const Color(0xFF192238),
                margin: const EdgeInsets.only(bottom: 5),
                child: ListTile(
                  dense: true,
                  selected: selected,
                  onTap: () => controller.selectLayer(layer.id),
                  leading: Icon(_layerIcon(layer.type), size: 19),
                  title: Text(
                    layer.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    layer.type,
                    style: const TextStyle(fontSize: 10),
                  ),
                  trailing: ReorderableDragStartListener(
                    index: index,
                    child: const Icon(Icons.drag_indicator_rounded, size: 18),
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
  final _canvasFocus = FocusNode(debugLabel: 'share theme canvas');
  bool _previewReady = false;

  @override
  void initState() {
    super.initState();
    _rebuildPreview();
  }

  @override
  void didUpdateWidget(_DesignCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    _rebuildPreview();
  }

  void _rebuildPreview() {
    if (_previewReady) _preview.dispose();
    final sample = widget.controller.theme.sampleContent;
    _content = ShareEditorContent(
      projectId: '${sample['projectId'] ?? 'sample_project'}',
      headline: '${sample['headline'] ?? 'Your headline'}',
      secondaryText: '${sample['secondaryText'] ?? 'Your supporting text'}',
      ownerName: '${sample['ownerName'] ?? 'Alex'}',
      ownerHandle: '${sample['ownerHandle'] ?? 'alexbuilds'}',
      avatar: const ShareImageValue.asset('assets/images/users/alex.jpg'),
      cover: const ShareImageValue.asset(
        'assets/images/backgrounds/startup.jpg',
      ),
      caption: '${sample['caption'] ?? ''}',
      publicLink: '${sample['publicLink'] ?? 'https://ptw.to'}',
      custom: sample,
    );
    _preview = ShareEditorController(
      theme: widget.controller.theme,
      content: _content,
      entitlements: (_) => widget.controller.previewPremium,
    );
    _preview.selectLook(widget.controller.selectedLookId);
    _previewReady = true;
  }

  @override
  void dispose() {
    _preview.dispose();
    _canvasFocus.dispose();
    super.dispose();
  }

  void _handleKey(KeyEvent event) {
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
                const Icon(
                  Icons.visibility_outlined,
                  size: 17,
                  color: Colors.white54,
                ),
                const SizedBox(width: 7),
                Text(
                  '${widget.controller.previewPremium ? 'Premium' : 'Free'} customer preview',
                  style: const TextStyle(color: Colors.white60, fontSize: 12),
                ),
                const Spacer(),
                Text(
                  '${widget.controller.theme.canvas.width.toInt()}×${widget.controller.theme.canvas.height.toInt()} logical',
                  style: const TextStyle(color: Colors.white38, fontSize: 11),
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
                return Center(
                  child: Container(
                    width: width,
                    height: height,
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.white24),
                      boxShadow: const [
                        BoxShadow(color: Colors.black87, blurRadius: 30),
                      ],
                    ),
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: GeneratedShareRenderer(
                            theme: widget.controller.theme,
                            content: _content,
                            value: _preview.value,
                          ),
                        ),
                        for (final layer in widget.controller.theme.layers)
                          if (layer.type != 'background' &&
                              layer.type != 'stickerWorkspace')
                            _BuilderLayerOverlay(
                              layer:
                                  layer.id == widget.controller.selectedLayerId
                                      ? widget.controller.editingLayer ?? layer
                                      : _preview.effectiveLayer(layer.id),
                              scale: scale,
                              selected:
                                  widget.controller.selectedLayerId == layer.id,
                              onSelect: () {
                                _canvasFocus.requestFocus();
                                widget.controller.selectLayer(layer.id);
                              },
                              onTransform:
                                  layer.id == widget.controller.selectedLayerId
                                      ? widget
                                          .controller
                                          .updateSelectedTransform
                                      : null,
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

final class _BuilderLayerOverlay extends StatelessWidget {
  const _BuilderLayerOverlay({
    required this.layer,
    required this.scale,
    required this.selected,
    required this.onSelect,
    required this.onTransform,
  });

  final ShareLayerConfig layer;
  final double scale;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<ShareLayerTransform>? onTransform;

  @override
  Widget build(BuildContext context) {
    final transform = layer.transform;
    return Positioned(
      left: transform.x * scale,
      top: transform.y * scale,
      width: transform.width * scale,
      height: transform.height * scale,
      child: Transform.rotate(
        angle: transform.rotation,
        child: GestureDetector(
          key: ValueKey('builder_canvas_layer_${layer.id}'),
          behavior: HitTestBehavior.translucent,
          onTap: onSelect,
          onPanUpdate:
              onTransform == null
                  ? null
                  : (details) => onTransform!(
                    transform.copyWith(
                      x: transform.x + details.delta.dx / scale,
                      y: transform.y + details.delta.dy / scale,
                    ),
                  ),
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
              if (selected && onTransform != null) ...[
                Positioned(
                  right: -8,
                  bottom: -8,
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onPanUpdate:
                        (details) => onTransform!(
                          transform.copyWith(
                            width: (transform.width + details.delta.dx / scale)
                                .clamp(8, 10000),
                            height: (transform.height +
                                    details.delta.dy / scale)
                                .clamp(8, 10000),
                          ),
                        ),
                    child: const _CanvasHandle(
                      icon: Icons.open_in_full_rounded,
                    ),
                  ),
                ),
                Positioned(
                  right: -8,
                  top: -8,
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onPanUpdate:
                        (details) => onTransform!(
                          transform.copyWith(
                            rotation:
                                transform.rotation + details.delta.dx * 0.012,
                          ),
                        ),
                    child: const _CanvasHandle(
                      icon: Icons.rotate_right_rounded,
                    ),
                  ),
                ),
              ],
            ],
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

final class _InspectorPane extends StatelessWidget {
  const _InspectorPane({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) {
    final layer = controller.editingLayer;
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF11192A),
        border: Border(left: BorderSide(color: Color(0xFF27324D))),
      ),
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const _PaneTitle(title: 'INSPECTOR'),
          _ThemeSection(controller: controller),
          _LookSection(controller: controller),
          if (layer != null) ...[
            _LayerSection(controller: controller, layer: layer),
            _StyleSection(controller: controller, layer: layer),
            _AccessSection(controller: controller, layer: layer),
          ],
          _ToolbarSection(controller: controller),
          _StickerCatalogSection(controller: controller),
          _AssetsSection(controller: controller),
        ],
      ),
    );
  }
}

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
      _StringField(
        label: 'Premium icon (workspace_premium, lock, diamond, star)',
        value: controller.theme.premiumIcon,
        onChanged: (value) => controller.updateMetadata(premiumIcon: value),
      ),
    ],
  );
}

final class _LookSection extends StatelessWidget {
  const _LookSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) {
    final look = controller.selectedLook;
    final background = controller.theme.background(
      look.backgroundId ?? controller.theme.defaultBackgroundId,
    );
    return ExpansionTile(
      initiallyExpanded: true,
      title: Text('Look: ${look.label}'),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        _StringField(
          label: 'Look label',
          value: look.label,
          onChanged: (value) => controller.updateSelectedLook(label: value),
        ),
        _AccessEditor(
          label: 'Look access',
          value: look.access,
          onChanged: (value) => controller.updateSelectedLook(access: value),
        ),
        DropdownButtonFormField<String>(
          value: background.id,
          decoration: const InputDecoration(labelText: 'Background'),
          items: [
            for (final item in controller.theme.backgrounds)
              DropdownMenuItem(value: item.id, child: Text(item.label)),
          ],
          onChanged: (value) {
            if (value != null) {
              controller.updateSelectedLook(backgroundId: value);
            }
          },
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
        _BackgroundFields(controller: controller, background: background),
        const Divider(),
        Row(
          children: [
            Expanded(
              child: Text(
                'Default stickers (${look.defaultStickers.length}/${controller.theme.maximumStickerCount})',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
            PopupMenuButton<String>(
              tooltip: 'Add default sticker',
              enabled:
                  look.defaultStickers.length <
                  controller.theme.maximumStickerCount,
              onSelected: controller.addLookSticker,
              itemBuilder:
                  (_) => [
                    for (final sticker in controller.theme.stickers)
                      PopupMenuItem(
                        value: sticker.id,
                        child: Text(sticker.label),
                      ),
                  ],
              icon: const Icon(Icons.add_reaction_outlined),
            ),
          ],
        ),
        for (final sticker in look.defaultStickers)
          _LookStickerFields(controller: controller, sticker: sticker),
      ],
    );
  }
}

final class _LookStickerFields extends StatelessWidget {
  const _LookStickerFields({required this.controller, required this.sticker});

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

final class _BackgroundFields extends StatelessWidget {
  const _BackgroundFields({required this.controller, required this.background});

  final ThemeBuilderController controller;
  final ShareBackgroundConfig background;

  @override
  Widget build(BuildContext context) {
    final properties = background.properties;
    void update(String key, Object? value) => controller.updateBackground(
      ShareBackgroundConfig(
        id: background.id,
        label: background.label,
        kind: background.kind,
        properties: {...properties, key: value},
        access: background.access,
      ),
    );
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
          _StringField(
            label: 'Color #AARRGGBB',
            value: '${properties['color'] ?? '#FF315CFF'}',
            onChanged: (value) => update('color', value),
          ),
        if ({'linear', 'radial', 'sweep'}.contains(background.kind)) ...[
          _StringField(
            label: 'Colors, comma-separated',
            value: (properties['colors'] as List<dynamic>).join(', '),
            onChanged:
                (value) => update(
                  'colors',
                  value.split(',').map((item) => item.trim()).toList(),
                ),
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
          _StringField(
            label: 'Binding or asset ID',
            value:
                '${properties['binding'] ?? properties['assetId'] ?? 'cover'}',
            onChanged: (value) => update('binding', value),
          ),
          _NumberField(
            label: 'Blur',
            value: _number(properties['blur'], 0),
            onChanged: (value) => update('blur', value),
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
          _StringField(
            label: 'Fallback asset ID',
            value: '${properties['fallbackAssetId'] ?? ''}',
            onChanged: (value) => update('fallbackAssetId', value),
          ),
          _StringField(
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
  const _LayerSection({required this.controller, required this.layer});

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    initiallyExpanded: true,
    title: Text('Layer: ${layer.label}'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      _StringField(
        label: 'Label',
        value: layer.label,
        onChanged:
            (value) => controller.updateLayer(
              (controller.selectedLayer ?? layer).copyWith(label: value),
            ),
      ),
      SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: const Text('Visible'),
        value: layer.visible,
        onChanged: controller.updateSelectedVisibility,
      ),
      if (layer.type == 'text' || layer.type == 'image')
        _StringField(
          label: 'Content binding',
          value: layer.binding ?? '',
          onChanged:
              (value) => controller.updateLayer(
                (controller.selectedLayer ?? layer).copyWith(
                  binding: value,
                  clearBinding: value.isEmpty,
                ),
              ),
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
  const _StyleSection({required this.controller, required this.layer});

  final ThemeBuilderController controller;
  final ShareLayerConfig layer;

  @override
  Widget build(BuildContext context) {
    final style = layer.style;
    return ExpansionTile(
      initiallyExpanded: true,
      title: const Text('Appearance'),
      childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      children: [
        if (layer.type == 'text') ...[
          _StringField(
            label: 'Font family',
            value: '${style['fontFamily'] ?? ''}',
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
          _StringField(
            label: 'Stroke color',
            value: '${style['strokeColor'] ?? '#FF000000'}',
            onChanged:
                (value) => controller.updateLayerStyle('strokeColor', value),
          ),
          _StringField(
            label: 'Text color',
            value: '${style['color'] ?? '#FFFFFFFF'}',
            onChanged: (value) => controller.updateLayerStyle('color', value),
          ),
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
          _StringField(
            label: 'Text background color',
            value: '${style['backgroundColor'] ?? '#00000000'}',
            onChanged:
                (value) =>
                    controller.updateLayerStyle('backgroundColor', value),
          ),
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
          DropdownButtonFormField<String>(
            value:
                controller.theme.assets.any(
                      (asset) =>
                          asset.kind == 'image' && asset.id == style['assetId'],
                    )
                    ? style['assetId'] as String
                    : null,
            decoration: InputDecoration(
              labelText:
                  layer.type == 'asset'
                      ? 'Static image asset'
                      : 'Default image asset',
            ),
            items: [
              for (final asset in controller.theme.assets)
                if (asset.kind == 'image')
                  DropdownMenuItem(value: asset.id, child: Text(asset.id)),
            ],
            onChanged: (value) => controller.updateLayerStyle('assetId', value),
          ),
          DropdownButtonFormField<String>(
            value:
                controller.theme.assets.any(
                      (asset) =>
                          asset.kind == 'image' &&
                          asset.id == style['fallbackAssetId'],
                    )
                    ? style['fallbackAssetId'] as String
                    : null,
            decoration: const InputDecoration(labelText: 'Fallback image'),
            items: [
              for (final asset in controller.theme.assets)
                if (asset.kind == 'image')
                  DropdownMenuItem(value: asset.id, child: Text(asset.id)),
            ],
            onChanged:
                (value) =>
                    controller.updateLayerStyle('fallbackAssetId', value),
          ),
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
          _StringField(
            label: 'Image alignment',
            value: '${style['imageAlignment'] ?? 'center'}',
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
          Row(
            children: [
              Expanded(
                child: _NumberField(
                  label: 'Opacity',
                  value: _number(style['opacity'], 1),
                  onChanged:
                      (value) => controller.updateLayerStyle(
                        'opacity',
                        value.clamp(0, 1),
                      ),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _NumberField(
                  label: 'Blur',
                  value: _number(style['blur'], 0),
                  onChanged:
                      (value) => controller.updateLayerStyle('blur', value),
                ),
              ),
            ],
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
          _StringField(
            label: 'Fill color',
            value: '${style['color'] ?? '#FFFFFFFF'}',
            onChanged: (value) => controller.updateLayerStyle('color', value),
          ),
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
          _StringField(
            label: 'Border color',
            value: '${style['borderColor'] ?? '#FFFFFFFF'}',
            onChanged:
                (value) => controller.updateLayerStyle('borderColor', value),
          ),
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
                child: _StringField(
                  label: 'Shadow color',
                  value: '${style['shadowColor'] ?? '#88000000'}',
                  onChanged:
                      (value) =>
                          controller.updateLayerStyle('shadowColor', value),
                ),
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

final class _ToolbarSection extends StatelessWidget {
  const _ToolbarSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: const Text('Customer toolbar'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      DropdownButtonFormField<String>(
        value: controller.theme.defaultToolbarGroupId,
        decoration: const InputDecoration(labelText: 'Default tab'),
        items: [
          for (final item in controller.theme.toolbar)
            DropdownMenuItem(value: item.id, child: Text(item.label)),
        ],
        onChanged: (value) {
          if (value != null) controller.setDefaultToolbarGroup(value);
        },
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
                      child: _StringField(
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
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        sticker.id,
                        style: const TextStyle(fontWeight: FontWeight.w700),
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

final class _AssetsSection extends StatelessWidget {
  const _AssetsSection({required this.controller});

  final ThemeBuilderController controller;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: Text('Assets (${controller.theme.assets.length})'),
    childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
    children: [
      for (final asset in controller.theme.assets)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            asset.kind == 'font'
                ? Icons.font_download_outlined
                : Icons.image_outlined,
          ),
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
  late final TextEditingController _key;

  @override
  void initState() {
    super.initState();
    _key = TextEditingController(
      text: widget.value.entitlementKey ?? 'premium',
    );
  }

  @override
  void didUpdateWidget(_AccessEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value.entitlementKey != widget.value.entitlementKey &&
        widget.value.entitlementKey != null) {
      _key.text = widget.value.entitlementKey!;
    }
  }

  @override
  void dispose() {
    _key.dispose();
    super.dispose();
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
                            mode == ShareAccessMode.free
                                ? null
                                : _key.text.trim(),
                      ),
                    ),
              ),
            ),
            if (widget.value.mode != ShareAccessMode.free) ...[
              const SizedBox(width: 7),
              SizedBox(
                width: 120,
                child: TextField(
                  controller: _key,
                  decoration: const InputDecoration(
                    labelText: 'Entitlement',
                    isDense: true,
                  ),
                  onSubmitted:
                      (value) => widget.onChanged(
                        ShareAccessPolicy(
                          mode: widget.value.mode,
                          entitlementKey: value.trim(),
                        ),
                      ),
                ),
              ),
            ],
          ],
        ),
      ],
    ),
  );
}

final class _StringField extends StatelessWidget {
  const _StringField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextFormField(
      key: ValueKey('$label:$value'),
      initialValue: value,
      decoration: InputDecoration(labelText: label, isDense: true),
      onFieldSubmitted: onChanged,
    ),
  );
}

final class _NumberField extends StatelessWidget {
  const _NumberField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final double value;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextFormField(
      key: ValueKey('$label:${value.toStringAsFixed(4)}'),
      initialValue: value.toStringAsFixed(
        value == value.roundToDouble() ? 0 : 3,
      ),
      keyboardType: const TextInputType.numberWithOptions(
        decimal: true,
        signed: true,
      ),
      decoration: InputDecoration(labelText: label, isDense: true),
      onFieldSubmitted: (raw) {
        final parsed = double.tryParse(raw);
        if (parsed != null) onChanged(parsed);
      },
    ),
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

double _number(Object? value, double fallback) =>
    value is num ? value.toDouble() : fallback;
