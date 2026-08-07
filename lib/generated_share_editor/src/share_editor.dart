import 'dart:async';

import 'package:flutter/material.dart';

import 'share_controller.dart';
import 'share_renderer.dart';
import 'share_theme.dart';
import 'share_value.dart';

final class ShareImageRequest {
  const ShareImageRequest({required this.layerId, required this.label});

  final String layerId;
  final String label;
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
    _selectedTool = _firstVisibleTool();
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
      if (layer.type == 'image') _selectedTool = 'images';
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
              hasChanges: _controller.hasChanges,
              onClose: widget.onClose,
              onReset: _reset,
              onMagic: _controller.cycleLook,
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
              onSelected: (id) => setState(() => _selectedTool = id),
              onLocked: widget.onLockedFeatureTap,
            ),
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
    'text' => _TextPanel(
      controller: _controller,
      textControllers: _textControllers,
      onLocked: widget.onLockedFeatureTap,
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
    _ => _PropertiesPanel(
      controller: _controller,
      onLocked: widget.onLockedFeatureTap,
    ),
  };

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
    if (_controller.accessState(preferred.access) != ShareAccessState.hidden) {
      return preferred.id;
    }
    for (final group in widget.theme.toolbar) {
      if (_controller.accessState(group.access) != ShareAccessState.hidden) {
        return group.id;
      }
    }
    return 'text';
  }
}

final class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.hasChanges,
    required this.onClose,
    required this.onReset,
    required this.onMagic,
  });

  final bool hasChanges;
  final VoidCallback? onClose;
  final VoidCallback onReset;
  final VoidCallback onMagic;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 52,
    child: Row(
      children: [
        IconButton(
          key: const ValueKey('share_back'),
          onPressed: onClose,
          color: Colors.white,
          icon: const Icon(Icons.close_rounded, size: 28),
        ),
        const Expanded(
          child: Text(
            'BUILD YOUR STORY',
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
        IconButton.filled(
          key: const ValueKey('share_generate_another'),
          onPressed: onMagic,
          style: IconButton.styleFrom(
            backgroundColor: const Color(0xFFFFE557),
            foregroundColor: const Color(0xFF111827),
          ),
          icon: const Icon(Icons.auto_awesome_rounded),
        ),
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
      (item) => controller.accessState(item.access) != ShareAccessState.hidden,
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
                label: group.label,
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

final class _TextPanel extends StatelessWidget {
  const _TextPanel({
    required this.controller,
    required this.textControllers,
    required this.onLocked,
  });

  final ShareEditorController controller;
  final Map<String, TextEditingController> textControllers;
  final ValueChanged<ShareLockedFeature>? onLocked;

  @override
  Widget build(BuildContext context) {
    final layers = controller.theme.layers.where((item) => item.type == 'text');
    return Column(
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: Padding(
            padding: const EdgeInsets.only(right: 8),
            child: TextButton.icon(
              key: const ValueKey('story_editor_done'),
              onPressed: () => FocusManager.instance.primaryFocus?.unfocus(),
              icon: const Icon(Icons.check_rounded),
              label: const Text('Done'),
            ),
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            children: [
              for (final layer in layers)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _LockedControl(
                    controller: controller,
                    layer: layer,
                    controlId: 'edit',
                    onLocked: onLocked,
                    child: TextField(
                      key: ValueKey(
                        layer.binding == 'headline'
                            ? 'story_headline_field'
                            : layer.binding == 'secondaryText'
                            ? 'story_dare_field'
                            : 'generated_text_${layer.id}',
                      ),
                      controller: textControllers.putIfAbsent(
                        layer.id,
                        () => TextEditingController(
                          text: '${controller.layerValue(layer.id) ?? ''}',
                        ),
                      ),
                      maxLength: _integer(layer.style['maxLength'], 200),
                      onTap: () => controller.selectLayer(layer.id),
                      onChanged:
                          (value) =>
                              controller.updateLayerValue(layer.id, value),
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        labelText: layer.label,
                        labelStyle: const TextStyle(color: Colors.white70),
                        counterStyle: const TextStyle(color: Colors.white54),
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
          ),
        ),
      ],
    );
  }
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
  Widget build(BuildContext context) => Column(
    children: [
      SizedBox(
        height: 70,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(12, 7, 12, 5),
          itemCount: controller.theme.looks.length,
          separatorBuilder: (_, __) => const SizedBox(width: 7),
          itemBuilder: (context, index) {
            final look = controller.theme.looks[index];
            final state = controller.accessState(look.access);
            if (state == ShareAccessState.hidden) {
              return const SizedBox.shrink();
            }
            return _AccessCard(
              key: ValueKey('story_look_${look.id}'),
              label: look.label,
              premiumIcon: _icon(controller.theme.premiumIcon),
              selected: controller.value.lookId == look.id,
              state: state,
              compact: true,
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
        ),
      ),
      Expanded(
        child: _BackgroundPanel(
          controller: controller,
          imageResolver: imageResolver,
          onLocked: onLocked,
        ),
      ),
    ],
  );
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
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;
  final ValueChanged<ShareLockedFeature>? onLocked;

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
                widget.controller.canAddSticker
                    ? '${widget.controller.value.stickers.length}/${widget.controller.theme.maximumStickerCount}'
                    : '${widget.controller.value.stickers.length}/${widget.controller.theme.maximumStickerCount} · Delete one to add',
                key: ValueKey(
                  widget.controller.canAddSticker
                      ? 'generated_sticker_count'
                      : 'studio_sticker_limit',
                ),
                style: const TextStyle(color: Colors.white60, fontSize: 11),
              ),
              const SizedBox(width: 8),
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
      (item) => item.type == 'image',
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
    this.compact = false,
  });

  final String label;
  final IconData premiumIcon;
  final ShareAccessState state;
  final VoidCallback onTap;
  final VoidCallback? onLocked;
  final bool selected;
  final Widget? preview;
  final bool compact;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: state == ShareAccessState.locked ? onLocked : onTap,
    borderRadius: BorderRadius.circular(12),
    child: Container(
      width: compact ? 112 : 92,
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
          if (!compact)
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
          if (!compact) const SizedBox(height: 4),
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
int _integer(Object? value, int fallback) =>
    value is num ? value.toInt() : fallback;
