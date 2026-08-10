import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'share_controller.dart';
import 'share_renderer.dart';
import 'share_theme.dart';
import 'share_value.dart';

enum ShareImagePurpose { layer, background, decoration }

final class ShareImageRequest {
  const ShareImageRequest({
    required this.layerId,
    required this.label,
    this.purpose = ShareImagePurpose.layer,
  });

  final String layerId;
  final String label;
  final ShareImagePurpose purpose;
}

typedef ShareImagePicker =
    Future<ShareImageValue?> Function(ShareImageRequest request);

final class GeneratedShareEditor extends StatefulWidget {
  const GeneratedShareEditor({
    required this.theme,
    required this.content,
    super.key,
    this.initialValue,
    this.controller,
    this.entitlements,
    this.imagePicker,
    this.imageResolver = defaultShareImageResolver,
    this.onChanged,
    this.onContinue,
    this.onClose,
    this.onLockedFeatureTap,
    this.onGenerateAnother,
    this.title = 'MAKE YOUR STORY',
  });

  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final ShareEditorValue? initialValue;
  final ShareEditorController? controller;
  final ShareEntitlementResolver? entitlements;
  final ShareImagePicker? imagePicker;
  final ShareImageProviderResolver imageResolver;
  final ValueChanged<ShareEditorValue>? onChanged;
  final VoidCallback? onContinue;
  final VoidCallback? onClose;
  final ValueChanged<ShareLockedFeature>? onLockedFeatureTap;
  final VoidCallback? onGenerateAnother;
  final String title;

  @override
  State<GeneratedShareEditor> createState() => _GeneratedShareEditorState();
}

final class _GeneratedShareEditorState extends State<GeneratedShareEditor> {
  late final ShareEditorController _controller;
  late final bool _ownsController;
  late String _selectedTool;
  final Map<String, TextEditingController> _textControllers = {};
  bool _pickingImage = false;

  @override
  void initState() {
    super.initState();
    _ownsController = widget.controller == null;
    _controller =
        widget.controller ??
        ShareEditorController(
          theme: widget.theme,
          content: widget.content,
          initialValue: widget.initialValue,
          entitlements: widget.entitlements,
        );
    _selectedTool =
        _controller.mode == ShareEditorMode.runtime ? '' : _firstVisibleTool();
    _controller.addListener(_changed);
  }

  @override
  void dispose() {
    _controller.removeListener(_changed);
    if (_ownsController) _controller.dispose();
    for (final controller in _textControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  void _changed() {
    final selectedLayerId = _controller.selectedLayerId;
    if (selectedLayerId != null) {
      final layer = _controller.theme.layer(selectedLayerId);
      if (layer.type == 'text') _selectedTool = 'text';
      if (layer.type == 'image') {
        _selectedTool = _hasTool('photo') ? 'photo' : 'images';
      }
    }
    if (_controller.selectedStickerId != null ||
        _controller.selectedOverlayId != null) {
      _selectedTool = _hasTool('decor') ? 'decor' : 'stickers';
    }
    widget.onChanged?.call(_controller.value);
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    return Material(
      color: const Color(0xFF10182A),
      child: SafeArea(
        child: Column(
          children: [
            _TopBar(
              title: widget.title,
              hasChanges: _controller.hasChanges,
              onClose: widget.onClose,
              onReset: _reset,
              onMagic: widget.onGenerateAnother ?? _controller.cycleLook,
              showMagic:
                  _controller.mode == ShareEditorMode.authoring ||
                  widget.onGenerateAnother != null,
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 4, 14, 8),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final width = (constraints.maxHeight *
                            widget.theme.canvas.width /
                            widget.theme.canvas.height)
                        .clamp(1.0, constraints.maxWidth);
                    return Center(
                      child: Container(
                        key: const ValueKey('story_builder_canvas'),
                        width: width,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(22),
                          border: Border.all(color: Colors.white24),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x66000000),
                              blurRadius: 22,
                              offset: Offset(0, 10),
                            ),
                          ],
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: GeneratedShareRenderer(
                          key: const ValueKey('share_preview'),
                          theme: widget.theme,
                          content: widget.content,
                          value: _controller.value,
                          controller: _controller,
                          imageResolver: widget.imageResolver,
                          editBackground: _selectedTool == 'photo',
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            _ToolBar(
              controller: _controller,
              selected: _selectedTool,
              onSelected: _selectTool,
              onLocked: widget.onLockedFeatureTap,
            ),
            if (_selectedTool.isNotEmpty)
              SizedBox(
                height: keyboardOpen ? 150 : 174,
                child: DecoratedBox(
                  decoration: const BoxDecoration(
                    color: Color(0xFF171F36),
                    border: Border(top: BorderSide(color: Color(0xFF2B3552))),
                  ),
                  child: _toolPanel(),
                ),
              ),
            if (widget.onContinue != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
                child: SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: FilledButton.icon(
                    key: const ValueKey('story_continue'),
                    onPressed: widget.onContinue,
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFF4066E),
                      foregroundColor: Colors.white,
                      shape: const StadiumBorder(),
                    ),
                    icon: const Icon(Icons.arrow_forward_rounded),
                    label: const Text(
                      'Continue',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _toolPanel() => switch (_selectedTool) {
    'templates' => _TemplatesPanel(controller: _controller),
    'text' => _TextPanel(
      controller: _controller,
      textControllers: _textControllers,
      onLocked: widget.onLockedFeatureTap,
      onDone: _closeTool,
    ),
    'looks' => _LooksPanel(
      controller: _controller,
      imageResolver: widget.imageResolver,
      onLocked: widget.onLockedFeatureTap,
    ),
    'backgrounds' => _BackgroundPanel(
      controller: _controller,
      imageResolver: widget.imageResolver,
      onLocked: widget.onLockedFeatureTap,
    ),
    'stickers' => _StickerPanel(
      controller: _controller,
      imageResolver: widget.imageResolver,
      onLocked: widget.onLockedFeatureTap,
    ),
    'images' => _ImagePanel(
      controller: _controller,
      busy: _pickingImage,
      onPick: _pickImage,
      onLocked: widget.onLockedFeatureTap,
    ),
    'photo' => _PhotoPanel(
      controller: _controller,
      busy: _pickingImage,
      onPickBackground: _pickBackground,
      onPickLayer: _pickImage,
      onLocked: widget.onLockedFeatureTap,
    ),
    'effects' => _EffectsPanel(controller: _controller),
    'decor' => _StickerPanel(
      controller: _controller,
      imageResolver: widget.imageResolver,
      onLocked: widget.onLockedFeatureTap,
      busy: _pickingImage,
      onUpload: _pickDecoration,
    ),
    _ => _PropertiesPanel(
      controller: _controller,
      onLocked: widget.onLockedFeatureTap,
    ),
  };

  void _selectTool(String id) {
    _controller.selectLayer(null);
    setState(() => _selectedTool = id);
  }

  void _closeTool() {
    FocusManager.instance.primaryFocus?.unfocus();
    _controller.selectLayer(null);
    setState(() => _selectedTool = '');
  }

  Future<void> _pickImage(ShareLayerConfig layer) async {
    final picker = widget.imagePicker;
    if (picker == null || _pickingImage) return;
    setState(() => _pickingImage = true);
    try {
      final image = await picker(
        ShareImageRequest(layerId: layer.id, label: layer.label),
      );
      if (image != null) _controller.updateLayerValue(layer.id, image);
    } finally {
      if (mounted) setState(() => _pickingImage = false);
    }
  }

  Future<void> _pickBackground() async {
    final picker = widget.imagePicker;
    if (picker == null || _pickingImage) return;
    setState(() => _pickingImage = true);
    try {
      final image = await picker(
        const ShareImageRequest(
          layerId: 'background',
          label: 'Background photo',
          purpose: ShareImagePurpose.background,
        ),
      );
      if (image != null) _controller.replaceBackgroundImage(image);
    } finally {
      if (mounted) setState(() => _pickingImage = false);
    }
  }

  Future<void> _pickDecoration() async {
    final picker = widget.imagePicker;
    if (picker == null || _pickingImage || !_controller.canAddDecoration) {
      return;
    }
    setState(() => _pickingImage = true);
    try {
      final image = await picker(
        const ShareImageRequest(
          layerId: 'decorations',
          label: 'Decoration',
          purpose: ShareImagePurpose.decoration,
        ),
      );
      if (image != null) _controller.addOverlay(image);
    } finally {
      if (mounted) setState(() => _pickingImage = false);
    }
  }

  void _reset() {
    _controller.reset();
    for (final entry in _textControllers.entries) {
      entry.value.text = '${_controller.layerValue(entry.key) ?? ''}';
    }
  }

  String _firstVisibleTool() {
    final preferred = widget.theme.toolbar.firstWhere(
      (item) => item.id == widget.theme.defaultToolbarGroupId,
    );
    if (_controller.accessState(preferred.access) != ShareAccessState.hidden &&
        _runtimeToolAvailable(_controller, preferred.id)) {
      return preferred.id;
    }
    for (final group in widget.theme.toolbar) {
      if (_controller.accessState(group.access) != ShareAccessState.hidden &&
          _runtimeToolAvailable(_controller, group.id)) {
        return group.id;
      }
    }
    return 'text';
  }

  bool _hasTool(String id) => widget.theme.toolbar.any((item) => item.id == id);
}

final class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.title,
    required this.hasChanges,
    required this.onClose,
    required this.onReset,
    required this.onMagic,
    required this.showMagic,
  });

  final String title;
  final bool hasChanges;
  final VoidCallback? onClose;
  final VoidCallback onReset;
  final VoidCallback onMagic;
  final bool showMagic;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 52,
    child: Row(
      children: [
        if (onClose == null)
          const SizedBox(width: 48)
        else
          IconButton(
            key: const ValueKey('share_back'),
            onPressed: onClose,
            color: Colors.white,
            icon: const Icon(Icons.close_rounded, size: 28),
          ),
        Expanded(
          child: Text(
            title,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontFamily: 'PtwLilitaOne',
              fontSize: 20,
              letterSpacing: 0.6,
            ),
          ),
        ),
        if (hasChanges)
          IconButton(
            key: const ValueKey('story_reset'),
            onPressed: onReset,
            color: Colors.white,
            icon: const Icon(Icons.restart_alt_rounded),
          )
        else
          const SizedBox(width: 48),
        if (showMagic)
          IconButton.filled(
            key: const ValueKey('share_generate_another'),
            tooltip: 'New options',
            onPressed: onMagic,
            style: IconButton.styleFrom(
              backgroundColor: const Color(0xFFFFE557),
              foregroundColor: const Color(0xFF111827),
            ),
            icon: const Icon(Icons.refresh_rounded),
          ),
        if (!showMagic) const SizedBox(width: 48),
        const SizedBox(width: 7),
      ],
    ),
  );
}

final class _ToolBar extends StatelessWidget {
  const _ToolBar({
    required this.controller,
    required this.selected,
    required this.onSelected,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final String selected;
  final ValueChanged<String> onSelected;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final groups = controller.theme.toolbar.where(
      (item) =>
          controller.accessState(item.access) != ShareAccessState.hidden &&
          _runtimeToolAvailable(controller, item.id),
    );
    return Container(
      height: 52,
      color: const Color(0xFF10182A),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          for (final group in groups)
            Expanded(
              child: _AccessButton(
                key: ValueKey('story_tool_${group.id}'),
                label: group.id == 'templates' ? 'Template' : group.label,
                icon: _icon(group.icon),
                premiumIcon: _icon(controller.theme.premiumIcon),
                selected: selected == group.id,
                state: controller.accessState(group.access),
                onTap: () => onSelected(group.id),
                onLocked:
                    onLocked == null
                        ? null
                        : () => onLocked!(
                          controller.lockedFeature(
                            id: group.id,
                            label: group.label,
                            access: group.access,
                          ),
                        ),
              ),
            ),
        ],
      ),
    );
  }
}

final class _TemplatesPanel extends StatelessWidget {
  const _TemplatesPanel({required this.controller});

  final ShareEditorController controller;

  @override
  Widget build(BuildContext context) => ListView.separated(
    key: const ValueKey('story_template_tray'),
    scrollDirection: Axis.horizontal,
    padding: const EdgeInsets.all(12),
    itemCount: controller.theme.templates.length,
    separatorBuilder: (_, __) => const SizedBox(width: 9),
    itemBuilder: (context, index) {
      final template = controller.theme.templates[index];
      final selected = template.id == controller.activeTemplate.id;
      return SizedBox(
        width: 142,
        child: ChoiceChip(
          key: ValueKey('story_template_${template.id}'),
          selected: selected,
          onSelected: (_) => controller.selectTemplate(template.id),
          avatar: Icon(switch (template.family) {
            ShareTemplateFamily.comparison => Icons.compare_rounded,
            ShareTemplateFamily.progress => Icons.trending_up_rounded,
            _ => Icons.crop_portrait_rounded,
          }, size: 18),
          label: Text(template.label, overflow: TextOverflow.ellipsis),
        ),
      );
    },
  );
}

final class _TextPanel extends StatelessWidget {
  const _TextPanel({
    required this.controller,
    required this.textControllers,
    required this.onLocked,
    required this.onDone,
  });

  final ShareEditorController controller;
  final Map<String, TextEditingController> textControllers;
  final ValueChanged<ShareLockedFeature>? onLocked;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final layers = controller.theme.layers
        .where(
          (item) =>
              item.type == 'text' &&
              item.control('edit') != null &&
              (controller.mode == ShareEditorMode.authoring ||
                  (controller.effectiveLayer(item.id).visible &&
                      controller.controlAccess(item.id, 'edit') !=
                          ShareAccessState.hidden)),
        )
        .toList(growable: false);
    final selected = layers.firstWhere(
      (item) => item.id == controller.selectedLayerId,
      orElse: () => layers.first,
    );
    return Column(
      children: [
        SizedBox(
          height: 34,
          child: Row(
            children: [
              const SizedBox(width: 12),
              Text(
                'STYLE: ${selected.label.toUpperCase()}',
                style: const TextStyle(
                  color: Colors.white60,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.6,
                ),
              ),
              const Spacer(),
              TextButton.icon(
                key: const ValueKey('story_editor_done'),
                onPressed: onDone,
                icon: const Icon(Icons.check_rounded),
                label: const Text('Done'),
              ),
              const SizedBox(width: 4),
            ],
          ),
        ),
        SizedBox(
          height: 58,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 5),
            child: Row(
              children: [
                for (var index = 0; index < layers.length; index++) ...[
                  if (index > 0) const SizedBox(width: 7),
                  Expanded(
                    child: _LockedControl(
                      controller: controller,
                      layer: layers[index],
                      controlId: 'edit',
                      onLocked: onLocked,
                      child: TextField(
                        key: ValueKey(
                          layers[index].binding == 'headline'
                              ? 'story_headline_field'
                              : layers[index].binding == 'secondaryText'
                              ? 'story_dare_field'
                              : 'generated_text_${layers[index].id}',
                        ),
                        controller: textControllers.putIfAbsent(
                          layers[index].id,
                          () => TextEditingController(
                            text:
                                '${controller.layerValue(layers[index].id) ?? ''}',
                          ),
                        ),
                        maxLength: _integer(
                          layers[index].style['maxLength'],
                          200,
                        ),
                        maxLines: 1,
                        onTap: () => controller.selectLayer(layers[index].id),
                        onChanged:
                            (value) => controller.updateLayerValue(
                              layers[index].id,
                              value,
                            ),
                        style: const TextStyle(
                          color: Color(0xFF10182A),
                          fontSize: 13,
                        ),
                        decoration: InputDecoration(
                          labelText: layers[index].label,
                          counterText: '',
                          isDense: true,
                          labelStyle: const TextStyle(color: Color(0xFF3D4963)),
                          enabledBorder: const OutlineInputBorder(
                            borderSide: BorderSide(color: Colors.white24),
                          ),
                          focusedBorder: const OutlineInputBorder(
                            borderSide: BorderSide(color: Color(0xFFFFE557)),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        if (controller.mode == ShareEditorMode.authoring)
          Expanded(
            child: _TextStyleBar(controller: controller, layer: selected),
          ),
      ],
    );
  }
}

final class _TextStyleBar extends StatelessWidget {
  const _TextStyleBar({required this.controller, required this.layer});

  final ShareEditorController controller;
  final ShareLayerConfig layer;

  static const _fonts = <(String, String, int)>[
    ('Clean', 'PtwRoboto', 700),
    ('Display', 'PtwLilitaOne', 400),
    ('Pixel', 'PtwPressStart2P', 400),
    ('Distressed', 'PtwRubikDirt', 400),
  ];
  static const _colors = <String>[
    '#FFFFFFFF',
    '#FF111827',
    '#FFF4066E',
    '#FFFFE557',
    '#FF4038B8',
    '#FFBFF7FF',
    '#FFFFB38A',
  ];

  @override
  Widget build(BuildContext context) {
    final style = controller.effectiveStyle(layer.id);
    final size = _number(style['fontSize'], 32).clamp(12, 72).toDouble();
    return ListView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(10, 3, 10, 7),
      children: [
        ActionChip(
          key: const ValueKey('story_text_font'),
          avatar: const Icon(Icons.font_download_outlined, size: 17),
          label: const Text('Font'),
          onPressed: () => _showFonts(context),
        ),
        const SizedBox(width: 6),
        ActionChip(
          key: const ValueKey('story_text_color'),
          avatar: Icon(
            Icons.circle,
            size: 17,
            color: shareColor(style['color']),
          ),
          label: const Text('Color'),
          onPressed: () => _showColors(context, effect: false),
        ),
        const SizedBox(width: 6),
        ActionChip(
          key: const ValueKey('story_text_effect'),
          avatar: const Icon(Icons.auto_fix_high_rounded, size: 17),
          label: const Text('Effect'),
          onPressed: () => _showEffects(context),
        ),
        const SizedBox(width: 6),
        ActionChip(
          key: const ValueKey('story_text_effect_color'),
          avatar: Icon(
            Icons.circle_outlined,
            size: 17,
            color: shareColor(
              style['shadowColor'] ?? style['strokeColor'],
              fallback: Colors.black,
            ),
          ),
          label: const Text('FX color'),
          onPressed: () => _showColors(context, effect: true),
        ),
        const SizedBox(width: 6),
        FilterChip(
          key: const ValueKey('story_text_italic'),
          label: const Text('Italic'),
          selected: style['italic'] == true,
          onSelected:
              (value) =>
                  controller.updateLayerProperty(layer.id, 'italic', value),
        ),
        const SizedBox(width: 6),
        IconButton.filledTonal(
          key: const ValueKey('story_text_align'),
          tooltip: 'Text alignment',
          onPressed: () {
            final current = style['textAlign'] as String? ?? 'center';
            final next = switch (current) {
              'left' => 'center',
              'center' => 'right',
              _ => 'left',
            };
            controller.updateLayerProperties(layer.id, {
              'textAlign': next,
              'alignment': switch (next) {
                'left' => 'centerLeft',
                'right' => 'centerRight',
                _ => 'center',
              },
            });
          },
          icon: Icon(switch (style['textAlign']) {
            'left' => Icons.format_align_left_rounded,
            'right' => Icons.format_align_right_rounded,
            _ => Icons.format_align_center_rounded,
          }),
        ),
        const SizedBox(width: 4),
        SizedBox(
          width: 170,
          child: Row(
            children: [
              const Text('Size', style: TextStyle(color: Colors.white60)),
              Expanded(
                child: Slider(
                  key: const ValueKey('story_text_size'),
                  value: size,
                  min: layer.id == 'secondary' ? 12 : 18,
                  max: layer.id == 'secondary' ? 40 : 72,
                  onChanged:
                      (value) => controller.updateLayerProperty(
                        layer.id,
                        'fontSize',
                        value,
                      ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _showFonts(BuildContext context) => showModalBottomSheet(
    context: context,
    backgroundColor: const Color(0xFF171F36),
    builder:
        (_) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final font in _fonts)
                ListTile(
                  key: ValueKey('story_font_${font.$2}'),
                  title: Text(
                    font.$1,
                    style: TextStyle(
                      color: Colors.white,
                      fontFamily: font.$2,
                      fontSize: 21,
                    ),
                  ),
                  subtitle: Text(
                    font.$2.replaceFirst('Ptw', ''),
                    style: const TextStyle(color: Colors.white54),
                  ),
                  onTap: () {
                    controller.updateLayerProperties(layer.id, {
                      'fontFamily': font.$2,
                      'fontWeight': font.$3,
                    });
                    Navigator.pop(context);
                  },
                ),
            ],
          ),
        ),
  );

  Future<void> _showColors(BuildContext context, {required bool effect}) =>
      showModalBottomSheet(
        context: context,
        backgroundColor: const Color(0xFF171F36),
        builder:
            (_) => SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Wrap(
                  spacing: 14,
                  runSpacing: 14,
                  children: [
                    for (final color in _colors)
                      InkWell(
                        key: ValueKey(
                          'story_${effect ? 'effect' : 'fill'}_color_$color',
                        ),
                        customBorder: const CircleBorder(),
                        onTap: () {
                          if (effect) {
                            controller.updateLayerProperties(layer.id, {
                              'shadowColor': color,
                              'strokeColor': color,
                            });
                          } else {
                            controller.updateLayerProperty(
                              layer.id,
                              'color',
                              color,
                            );
                          }
                          Navigator.pop(context);
                        },
                        child: Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: shareColor(color),
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white70, width: 2),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
      );

  Future<void> _showEffects(BuildContext context) => showModalBottomSheet(
    context: context,
    backgroundColor: const Color(0xFF171F36),
    builder:
        (_) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              _effectTile(context, 'None', {
                'shadowBlur': 0.0,
                'shadowX': 0.0,
                'shadowY': 0.0,
                'strokeWidth': 0.0,
              }),
              _effectTile(context, 'Soft shadow', {
                'shadowBlur': 8.0,
                'shadowX': 0.0,
                'shadowY': 4.0,
                'strokeWidth': 0.0,
              }),
              _effectTile(context, 'Hard offset', {
                'shadowBlur': 0.0,
                'shadowX': 3.0,
                'shadowY': 4.0,
                'strokeWidth': 0.0,
              }),
              _effectTile(context, 'Outline', {
                'shadowBlur': 0.0,
                'shadowX': 0.0,
                'shadowY': 0.0,
                'strokeWidth': 2.0,
              }),
            ],
          ),
        ),
  );

  Widget _effectTile(
    BuildContext context,
    String label,
    Map<String, Object?> values,
  ) => ListTile(
    title: Text(label, style: const TextStyle(color: Colors.white)),
    onTap: () {
      controller.updateLayerProperties(layer.id, values);
      Navigator.pop(context);
    },
  );
}

final class _LooksPanel extends StatelessWidget {
  const _LooksPanel({
    required this.controller,
    required this.imageResolver,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final looks = controller.theme.looks
        .where((item) => item.editorVisible)
        .toList(growable: false);
    return ListView.separated(
      key: const ValueKey('story_look_tray'),
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 9),
      itemCount: looks.length,
      separatorBuilder: (_, __) => const SizedBox(width: 9),
      itemBuilder: (context, index) {
        final look = looks[index];
        final state = controller.accessState(look.access);
        if (state == ShareAccessState.hidden) return const SizedBox.shrink();
        return _AccessCard(
          key: ValueKey('story_look_${look.id}'),
          label: look.label,
          premiumIcon: _icon(controller.theme.premiumIcon),
          selected: controller.value.lookId == look.id,
          state: state,
          preview: _LookSwatch(look: look),
          onTap: () => controller.selectLook(look.id),
          onLocked:
              onLocked == null
                  ? null
                  : () => onLocked!(
                    controller.lockedFeature(
                      id: look.id,
                      label: look.label,
                      access: look.access,
                    ),
                  ),
        );
      },
    );
  }
}

final class _LookSwatch extends StatelessWidget {
  const _LookSwatch({required this.look});

  final ShareLookConfig look;

  @override
  Widget build(BuildContext context) {
    final edit = look.backgroundTreatment;
    return Stack(
      fit: StackFit.expand,
      children: [
        ColoredBox(
          color: shareColor(
            edit.tintColor,
            fallback: const Color(0xFF27324D),
          ).withValues(alpha: math.max(0.35, edit.tintOpacity)),
        ),
        if (edit.texture != ShareBackgroundTexture.none)
          Center(
            child: Icon(
              switch (edit.texture) {
                ShareBackgroundTexture.grain => Icons.grain_rounded,
                ShareBackgroundTexture.stripes => Icons.horizontal_rule,
                ShareBackgroundTexture.blobs => Icons.gesture_rounded,
                ShareBackgroundTexture.iridescent => Icons.auto_awesome_rounded,
                ShareBackgroundTexture.none => Icons.image_outlined,
              },
              color: Colors.white,
              size: 28,
            ),
          ),
      ],
    );
  }
}

final class _BackgroundPanel extends StatelessWidget {
  const _BackgroundPanel({
    required this.controller,
    required this.imageResolver,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    key: const ValueKey('story_background_tray'),
    scrollDirection: Axis.horizontal,
    padding: const EdgeInsets.all(12),
    child: Row(
      children: [
        for (final item in controller.theme.backgrounds)
          if (controller.accessState(item.access) != ShareAccessState.hidden)
            Padding(
              padding: const EdgeInsets.only(right: 9),
              child: _AccessCard(
                key: ValueKey('story_background_${item.id}'),
                label: item.label,
                premiumIcon: _icon(controller.theme.premiumIcon),
                selected: controller.value.backgroundId == item.id,
                state: controller.accessState(item.access),
                preview: _BackgroundSwatch(background: item),
                onTap: () => controller.selectBackground(item.id),
                onLocked:
                    onLocked == null
                        ? null
                        : () => onLocked!(
                          controller.lockedFeature(
                            id: item.id,
                            label: item.label,
                            access: item.access,
                          ),
                        ),
              ),
            ),
      ],
    ),
  );
}

final class _StickerPanel extends StatefulWidget {
  const _StickerPanel({
    required this.controller,
    required this.imageResolver,
    required this.onLocked,
    this.busy = false,
    this.onUpload,
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;
  final ValueChanged<ShareLockedFeature>? onLocked;
  final bool busy;
  final VoidCallback? onUpload;

  @override
  State<_StickerPanel> createState() => _StickerPanelState();
}

final class _StickerPanelState extends State<_StickerPanel> {
  String? _category;

  @override
  Widget build(BuildContext context) {
    final categories = widget.controller.theme.stickers
        .map((sticker) => sticker.category)
        .toSet()
        .toList(growable: false);
    final selectedCategory =
        categories.contains(_category) ? _category : categories.firstOrNull;
    final stickers = widget.controller.theme.stickers
        .where((sticker) => sticker.category == selectedCategory)
        .toList(growable: false);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 5, 12, 0),
          child: Row(
            children: [
              Text(
                widget.controller.canAddDecoration
                    ? '${widget.controller.decorationCount}/${widget.controller.theme.maximumDecorationCount} layers'
                    : '${widget.controller.decorationCount}/${widget.controller.theme.maximumDecorationCount} · Delete one to add',
                key: ValueKey(
                  widget.controller.canAddSticker
                      ? 'generated_sticker_count'
                      : 'studio_sticker_limit',
                ),
                style: const TextStyle(color: Colors.white60, fontSize: 11),
              ),
              const SizedBox(width: 8),
              if (widget.onUpload != null) ...[
                IconButton.filledTonal(
                  key: const ValueKey('story_upload_decoration'),
                  tooltip: 'Upload decoration',
                  visualDensity: VisualDensity.compact,
                  onPressed:
                      widget.busy || !widget.controller.canAddDecoration
                          ? null
                          : widget.onUpload,
                  icon:
                      widget.busy
                          ? const SizedBox.square(
                            dimension: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                          : const Icon(Icons.add_photo_alternate_outlined),
                ),
                const SizedBox(width: 5),
              ],
              Expanded(
                child: SizedBox(
                  height: 28,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: categories.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 5),
                    itemBuilder: (context, index) {
                      final category = categories[index];
                      return ChoiceChip(
                        label: Text(category),
                        selected: category == selectedCategory,
                        onSelected: (_) => setState(() => _category = category),
                        visualDensity: VisualDensity.compact,
                      );
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.separated(
            key: const ValueKey('story_sticker_tray'),
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(7),
            itemCount: stickers.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final sticker = stickers[index];
              final state = widget.controller.accessState(sticker.access);
              if (state == ShareAccessState.hidden) {
                return const SizedBox.shrink();
              }
              final asset = widget.controller.theme.asset(sticker.assetId);
              final image =
                  asset.embeddedBytes == null
                      ? ShareImageValue.asset(asset.path!)
                      : ShareImageValue.memory(
                        asset.embeddedBytes!,
                        mimeType: asset.mimeType,
                      );
              return _AccessCard(
                key: ValueKey('story_sticker_${sticker.id}'),
                label: sticker.label,
                premiumIcon: _icon(widget.controller.theme.premiumIcon),
                state: state,
                preview:
                    widget.imageResolver(image) == null
                        ? const Icon(Icons.broken_image_outlined)
                        : Image(
                          image: widget.imageResolver(image)!,
                          fit: BoxFit.contain,
                        ),
                onTap: () => widget.controller.addSticker(sticker.id),
                onLocked:
                    widget.onLocked == null
                        ? null
                        : () => widget.onLocked!(
                          widget.controller.lockedFeature(
                            id: sticker.id,
                            label: sticker.label,
                            access: sticker.access,
                          ),
                        ),
              );
            },
          ),
        ),
      ],
    );
  }
}

final class _ImagePanel extends StatelessWidget {
  const _ImagePanel({
    required this.controller,
    required this.busy,
    required this.onPick,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final bool busy;
  final ValueChanged<ShareLayerConfig> onPick;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final layers = controller.theme.layers.where(
      (item) =>
          item.type == 'image' &&
          controller.effectiveLayer(item.id).visible &&
          controller.controlAccess(item.id, 'edit') != ShareAccessState.hidden,
    );
    return ListView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.all(12),
      children: [
        for (final layer in layers)
          Padding(
            padding: const EdgeInsets.only(right: 9),
            child: _LockedControl(
              controller: controller,
              layer: layer,
              controlId: 'edit',
              onLocked: onLocked,
              child: FilledButton.icon(
                onPressed: busy ? null : () => onPick(layer),
                icon: const Icon(Icons.photo_library_outlined),
                label: Text(busy ? 'Opening…' : 'Replace ${layer.label}'),
              ),
            ),
          ),
      ],
    );
  }
}

final class _PhotoPanel extends StatelessWidget {
  const _PhotoPanel({
    required this.controller,
    required this.busy,
    required this.onPickBackground,
    required this.onPickLayer,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final bool busy;
  final VoidCallback onPickBackground;
  final ValueChanged<ShareLayerConfig> onPickLayer;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final editableImages = controller.theme.layers
        .where(
          (item) =>
              item.type == 'image' &&
              controller.effectiveLayer(item.id).visible &&
              controller.controlAccess(item.id, 'edit') !=
                  ShareAccessState.hidden,
        )
        .toList(growable: false);
    final edit = controller.value.backgroundEdit;
    return Column(
      children: [
        SizedBox(
          height: 52,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(10, 7, 10, 4),
            children: [
              FilterChip(
                key: const ValueKey('story_use_project_photo'),
                avatar: const Icon(Icons.image_outlined, size: 17),
                label: const Text('Project photo'),
                selected: edit.image == null,
                onSelected: (_) => controller.useProjectBackground(),
              ),
              const SizedBox(width: 7),
              ActionChip(
                key: const ValueKey('story_replace_background'),
                avatar:
                    busy
                        ? const SizedBox.square(
                          dimension: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Icon(Icons.photo_library_outlined, size: 17),
                label: Text(busy ? 'Opening…' : 'Choose photo'),
                onPressed: busy ? null : onPickBackground,
              ),
              const SizedBox(width: 7),
              for (final imageLayer in editableImages) ...[
                _LockedControl(
                  controller: controller,
                  layer: imageLayer,
                  controlId: 'edit',
                  onLocked: onLocked,
                  child: ActionChip(
                    key: ValueKey('story_replace_${imageLayer.id}'),
                    avatar: const Icon(
                      Icons.add_photo_alternate_outlined,
                      size: 17,
                    ),
                    label: Text(imageLayer.label),
                    onPressed: busy ? null : () => onPickLayer(imageLayer),
                  ),
                ),
                const SizedBox(width: 7),
              ],
              ActionChip(
                key: const ValueKey('story_reset_crop'),
                avatar: const Icon(Icons.center_focus_strong, size: 17),
                label: const Text('Reset crop'),
                onPressed:
                    () => controller.updateBackgroundCrop(
                      alignmentX: 0,
                      alignmentY: 0,
                      zoom: 1,
                    ),
              ),
            ],
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 7),
            child: Row(
              children: [
                const Icon(Icons.zoom_in_rounded, color: Colors.white60),
                Expanded(
                  child: Slider(
                    key: const ValueKey('story_background_zoom'),
                    value: edit.zoom,
                    min: 1,
                    max: 4,
                    divisions: 30,
                    onChanged:
                        (value) => controller.updateBackgroundCrop(zoom: value),
                  ),
                ),
                Text(
                  '${edit.zoom.toStringAsFixed(1)}×',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
                const SizedBox(width: 10),
                const Flexible(
                  child: Text(
                    'Drag or pinch the photo on the canvas',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: Colors.white54, fontSize: 11),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

final class _EffectsPanel extends StatelessWidget {
  const _EffectsPanel({required this.controller});

  final ShareEditorController controller;

  static const _filters = <(String, double, double, double, String, double)>[
    ('Natural', 0, 1, 1, '#FFFFFFFF', 0),
    ('B&W', 0.04, 1.08, 0, '#FFFFFFFF', 0),
    ('Punch', 0.02, 1.35, 1.35, '#FFFFFFFF', 0),
    ('Warm', 0.06, 1.08, 0.85, '#FFFF8A5B', 0.22),
    ('Pastel', 0.16, 0.82, 0.62, '#FFFFB7E8', 0.3),
  ];

  @override
  Widget build(BuildContext context) {
    final edit = controller.value.backgroundEdit;
    return Column(
      children: [
        SizedBox(
          height: 50,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(10, 6, 10, 4),
            itemCount: _filters.length + 1,
            separatorBuilder: (_, __) => const SizedBox(width: 6),
            itemBuilder: (context, index) {
              if (index == _filters.length) {
                return ActionChip(
                  key: const ValueKey('story_effect_adjust'),
                  avatar: const Icon(Icons.tune_rounded, size: 17),
                  label: const Text('Adjust'),
                  onPressed: () => _showAdjustments(context),
                );
              }
              final filter = _filters[index];
              return ActionChip(
                key: ValueKey('story_filter_${filter.$1.toLowerCase()}'),
                label: Text(filter.$1),
                onPressed:
                    () => controller.updateBackground(
                      edit.copyWith(
                        brightness: filter.$2,
                        contrast: filter.$3,
                        saturation: filter.$4,
                        tintColor: filter.$5,
                        tintOpacity: filter.$6,
                      ),
                    ),
              );
            },
          ),
        ),
        Expanded(
          child: Row(
            children: [
              Expanded(
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(10, 4, 6, 7),
                  itemCount: ShareBackgroundTexture.values.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 6),
                  itemBuilder: (context, index) {
                    final texture = ShareBackgroundTexture.values[index];
                    return ChoiceChip(
                      key: ValueKey('story_texture_${texture.name}'),
                      label: Text(_textureLabel(texture)),
                      selected: edit.texture == texture,
                      onSelected:
                          (_) => controller.updateBackground(
                            edit.copyWith(
                              texture: texture,
                              textureIntensity:
                                  texture == ShareBackgroundTexture.none
                                      ? 0
                                      : math.max(edit.textureIntensity, 0.28),
                            ),
                          ),
                    );
                  },
                ),
              ),
              if (edit.texture != ShareBackgroundTexture.none)
                SizedBox(
                  width: 128,
                  child: Slider(
                    key: const ValueKey('story_texture_intensity'),
                    value: edit.textureIntensity,
                    min: 0,
                    max: 1,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(textureIntensity: value),
                        ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _showAdjustments(BuildContext context) => showModalBottomSheet(
    context: context,
    backgroundColor: const Color(0xFF171F36),
    isScrollControlled: true,
    builder:
        (_) => SafeArea(
          child: AnimatedBuilder(
            animation: controller,
            builder: (context, __) {
              final edit = controller.value.backgroundEdit;
              return ListView(
                shrinkWrap: true,
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
                children: [
                  const Text(
                    'PHOTO ADJUSTMENTS',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.8,
                    ),
                  ),
                  _SliderRow(
                    label: 'Blur',
                    value: edit.blur,
                    minimum: 0,
                    maximum: 30,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(blur: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Brightness',
                    value: edit.brightness,
                    minimum: -1,
                    maximum: 1,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(brightness: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Contrast',
                    value: edit.contrast,
                    minimum: 0.5,
                    maximum: 2,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(contrast: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Saturation',
                    value: edit.saturation,
                    minimum: 0,
                    maximum: 2,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(saturation: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Dim',
                    value: edit.overlayOpacity,
                    minimum: 0,
                    maximum: 1,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(overlayOpacity: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Photo visibility',
                    value: edit.imageOpacity,
                    minimum: 0.2,
                    maximum: 1,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(imageOpacity: value),
                        ),
                  ),
                  _SliderRow(
                    label: 'Texture scale',
                    value: edit.textureScale,
                    minimum: 0.5,
                    maximum: 4,
                    onChanged:
                        (value) => controller.updateBackground(
                          edit.copyWith(textureScale: value),
                        ),
                  ),
                ],
              );
            },
          ),
        ),
  );

  static String _textureLabel(ShareBackgroundTexture value) => switch (value) {
    ShareBackgroundTexture.none => 'None',
    ShareBackgroundTexture.grain => 'Grain',
    ShareBackgroundTexture.stripes => 'Stripes',
    ShareBackgroundTexture.blobs => 'Blobs',
    ShareBackgroundTexture.iridescent => 'Holo',
  };
}

final class _PropertiesPanel extends StatelessWidget {
  const _PropertiesPanel({required this.controller, required this.onLocked});

  final ShareEditorController controller;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final layerId = controller.selectedLayerId;
    final stickerId = controller.selectedStickerId;
    if (stickerId != null) {
      final sticker = controller.value.stickers.firstWhere(
        (item) => item.instanceId == stickerId,
      );
      final config = controller.theme.sticker(sticker.stickerId);
      final workspace = controller.theme.layers.firstWhere(
        (item) => item.type == 'stickerWorkspace',
      );
      return ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Text(
            config.label,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          if (config.canResize)
            _LockedControl(
              controller: controller,
              layer: workspace,
              controlId: 'resize',
              onLocked: onLocked,
              child: _SliderRow(
                label: 'Size',
                value: sticker.scale,
                minimum: config.minimumScale,
                maximum: config.maximumScale,
                onChanged:
                    (value) =>
                        controller.updateSticker(stickerId, scale: value),
              ),
            ),
          if (config.canRotate)
            _LockedControl(
              controller: controller,
              layer: workspace,
              controlId: 'rotate',
              onLocked: onLocked,
              child: _SliderRow(
                label: 'Rotation',
                value: sticker.rotation,
                minimum: -3.1416,
                maximum: 3.1416,
                onChanged:
                    (value) =>
                        controller.updateSticker(stickerId, rotation: value),
              ),
            ),
        ],
      );
    }
    if (layerId == null) {
      return const Center(
        child: Text(
          'Select a layer to edit its properties',
          style: TextStyle(color: Colors.white60),
        ),
      );
    }
    final layer = controller.theme.layer(layerId);
    final style = controller.effectiveStyle(layerId);
    final controls = layer.controls.where(
      (item) => !{'edit', 'move', 'resize', 'rotate'}.contains(item.id),
    );
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Text(
          layer.label,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
        for (final control in controls)
          _LockedControl(
            controller: controller,
            layer: layer,
            controlId: control.id,
            onLocked: onLocked,
            child: _PropertyControl(
              controller: controller,
              layerId: layerId,
              control: control,
              value:
                  style[control.id] ??
                  control.defaultValue ??
                  (control.options.isEmpty ? null : control.options.first),
            ),
          ),
      ],
    );
  }
}

final class _PropertyControl extends StatelessWidget {
  const _PropertyControl({
    required this.controller,
    required this.layerId,
    required this.control,
    required this.value,
  });

  final ShareEditorController controller;
  final String layerId;
  final ShareControlConfig control;
  final Object? value;

  @override
  Widget build(BuildContext context) => switch (control.kind) {
    ShareControlKind.number => _SliderRow(
      label: control.label,
      value: _number(value, control.minimum ?? 0),
      minimum: control.minimum ?? 0,
      maximum: control.maximum ?? 100,
      onChanged:
          (next) => controller.updateLayerProperty(layerId, control.id, next),
    ),
    ShareControlKind.choice => DropdownButtonFormField<String>(
      value: control.options.contains('$value') ? '$value' : null,
      decoration: InputDecoration(labelText: control.label),
      items: [
        for (final option in control.options)
          DropdownMenuItem(value: option, child: Text(option)),
      ],
      onChanged:
          (next) => controller.updateLayerProperty(layerId, control.id, next),
    ),
    ShareControlKind.toggle => SwitchListTile.adaptive(
      value: value == true,
      title: Text(control.label),
      onChanged:
          (next) => controller.updateLayerProperty(layerId, control.id, next),
    ),
    ShareControlKind.text || ShareControlKind.color => TextFormField(
      initialValue: '${value ?? ''}',
      decoration: InputDecoration(labelText: control.label),
      onFieldSubmitted:
          (next) => controller.updateLayerProperty(layerId, control.id, next),
    ),
    ShareControlKind.action => const SizedBox.shrink(),
  };
}

final class _LockedControl extends StatelessWidget {
  const _LockedControl({
    required this.controller,
    required this.layer,
    required this.controlId,
    required this.onLocked,
    required this.child,
  });

  final ShareEditorController controller;
  final ShareLayerConfig layer;
  final String controlId;
  final ValueChanged<ShareLockedFeature>? onLocked;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final control = layer.control(controlId);
    if (control == null) return const SizedBox.shrink();
    final layerState = controller.accessState(layer.access);
    final state =
        layerState == ShareAccessState.available
            ? controller.accessState(control.access)
            : layerState;
    final lockedAccess =
        layerState == ShareAccessState.available
            ? control.access
            : layer.access;
    if (state == ShareAccessState.hidden) return const SizedBox.shrink();
    if (state == ShareAccessState.available) return child;
    return Stack(
      children: [
        IgnorePointer(child: Opacity(opacity: 0.45, child: child)),
        Positioned.fill(
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap:
                  onLocked == null
                      ? null
                      : () => onLocked!(
                        controller.lockedFeature(
                          id: '${layer.id}.$controlId',
                          label: control.label,
                          access: lockedAccess,
                        ),
                      ),
              child: Align(
                alignment: Alignment.topRight,
                child: Icon(
                  _icon(controller.theme.premiumIcon),
                  color: const Color(0xFFFFE557),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

final class _AccessButton extends StatelessWidget {
  const _AccessButton({
    required this.label,
    required this.icon,
    required this.premiumIcon,
    required this.selected,
    required this.state,
    required this.onTap,
    required this.onLocked,
    super.key,
  });

  final String label;
  final IconData icon;
  final IconData premiumIcon;
  final bool selected;
  final ShareAccessState state;
  final VoidCallback onTap;
  final VoidCallback? onLocked;

  @override
  Widget build(BuildContext context) => TextButton.icon(
    onPressed: state == ShareAccessState.locked ? onLocked : onTap,
    style: TextButton.styleFrom(
      foregroundColor: selected ? const Color(0xFFFFE557) : Colors.white70,
      padding: const EdgeInsets.symmetric(horizontal: 4),
    ),
    icon: Stack(
      clipBehavior: Clip.none,
      children: [
        Icon(icon, size: 20),
        if (state == ShareAccessState.locked)
          Positioned(
            right: -8,
            top: -7,
            child: Icon(premiumIcon, size: 12, color: Color(0xFFFFE557)),
          ),
      ],
    ),
    label: Text(label, overflow: TextOverflow.ellipsis),
  );
}

final class _AccessCard extends StatelessWidget {
  const _AccessCard({
    required this.label,
    required this.premiumIcon,
    required this.state,
    required this.onTap,
    required this.onLocked,
    super.key,
    this.selected = false,
    this.preview,
  });

  final String label;
  final IconData premiumIcon;
  final ShareAccessState state;
  final VoidCallback onTap;
  final VoidCallback? onLocked;
  final bool selected;
  final Widget? preview;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: state == ShareAccessState.locked ? onLocked : onTap,
    borderRadius: BorderRadius.circular(12),
    child: Container(
      width: 92,
      padding: const EdgeInsets.all(7),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFF334068) : const Color(0xFF222C49),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: selected ? const Color(0xFFFFE557) : Colors.white12,
          width: selected ? 2 : 1,
        ),
      ),
      child: Column(
        children: [
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                preview ??
                    Center(
                      child: Text(
                        label.characters.first,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 26,
                        ),
                      ),
                    ),
                if (state == ShareAccessState.locked)
                  Align(
                    alignment: Alignment.topRight,
                    child: Icon(
                      premiumIcon,
                      color: Color(0xFFFFE557),
                      size: 18,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Colors.white, fontSize: 11),
          ),
        ],
      ),
    ),
  );
}

final class _BackgroundSwatch extends StatelessWidget {
  const _BackgroundSwatch({required this.background});

  final ShareBackgroundConfig background;

  @override
  Widget build(BuildContext context) {
    final properties = background.properties;
    if (background.kind == 'solid') {
      return ColoredBox(color: shareColor(properties['color']));
    }
    if ({'linear', 'radial', 'sweep'}.contains(background.kind)) {
      final colors =
          (properties['colors'] as List<dynamic>).map(shareColor).toList();
      return DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: colors),
          borderRadius: BorderRadius.circular(7),
        ),
      );
    }
    return const ColoredBox(
      color: Color(0xFF34415F),
      child: Icon(Icons.photo_outlined, color: Colors.white),
    );
  }
}

final class _SliderRow extends StatelessWidget {
  const _SliderRow({
    required this.label,
    required this.value,
    required this.minimum,
    required this.maximum,
    required this.onChanged,
  });

  final String label;
  final double value;
  final double minimum;
  final double maximum;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      SizedBox(
        width: 76,
        child: Text(label, style: const TextStyle(color: Colors.white70)),
      ),
      Expanded(
        child: Slider(
          value: value.clamp(minimum, maximum),
          min: minimum,
          max: maximum,
          onChanged: onChanged,
        ),
      ),
      SizedBox(
        width: 48,
        child: Text(
          value.toStringAsFixed(1),
          style: const TextStyle(color: Colors.white60),
        ),
      ),
    ],
  );
}

IconData _icon(String value) => switch (value) {
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

bool _runtimeToolAvailable(ShareEditorController controller, String id) {
  if (controller.mode == ShareEditorMode.authoring) return true;
  final permissions = controller.activeTemplate.runtimePermissions;
  return switch (id) {
    'templates' =>
      controller.theme.templates.length > 1 &&
          (controller.allowRuntimeTemplateSelection ||
              permissions.userCanChooseAlternateTemplate),
    'text' => controller.theme.layers.any(
      (layer) =>
          layer.type == 'text' &&
          controller.effectiveLayer(layer.id).visible &&
          controller.controlAccess(layer.id, 'edit') != ShareAccessState.hidden,
    ),
    'photo' ||
    'images' => permissions.userCanReplaceMedia || permissions.userCanCropMedia,
    _ => false,
  };
}

double _number(Object? value, double fallback) =>
    value is num ? value.toDouble() : fallback;
int _integer(Object? value, int fallback) =>
    value is num ? value.toInt() : fallback;
