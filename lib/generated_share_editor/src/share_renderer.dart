import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';

import 'share_controller.dart';
import 'share_theme.dart';
import 'share_value.dart';

typedef ShareImageProviderResolver =
    ImageProvider<Object>? Function(ShareImageValue image);

typedef ShareComponentBuilder = Widget Function(ShareComponentContext context);
typedef ShareComponentValidator = void Function(ShareLayerConfig layer);

final class ShareComponentDefinition {
  const ShareComponentDefinition({
    required this.builder,
    this.inspectorProperties = const [],
    this.interactions = const {'select', 'move', 'resize', 'rotate'},
    this.validator,
  });

  final ShareComponentBuilder builder;
  final List<String> inspectorProperties;
  final Set<String> interactions;
  final ShareComponentValidator? validator;
}

final class ShareComponentContext {
  const ShareComponentContext({
    required this.context,
    required this.theme,
    required this.layer,
    required this.value,
    required this.style,
    required this.scale,
    required this.imageResolver,
  });

  final BuildContext context;
  final ShareThemeConfig theme;
  final ShareLayerConfig layer;
  final Object? value;
  final Map<String, Object?> style;
  final double scale;
  final ShareImageProviderResolver imageResolver;
}

final class ShareComponentRegistry {
  ShareComponentRegistry({
    Map<String, ShareComponentBuilder> builders = const {},
    Map<String, ShareComponentDefinition> definitions = const {},
  }) : _definitions = {
         ..._builtIns,
         for (final entry in builders.entries)
           entry.key: ShareComponentDefinition(builder: entry.value),
         ...definitions,
       };

  final Map<String, ShareComponentDefinition> _definitions;

  static final Map<String, ShareComponentDefinition> _builtIns = {
    'text': const ShareComponentDefinition(
      builder: _buildText,
      inspectorProperties: [
        'fontFamily',
        'fontSize',
        'fontWeight',
        'color',
        'textAlign',
        'alignment',
        'autoSize',
        'maxLines',
        'backgroundColor',
        'borderRadius',
        'borderWidth',
        'shadowBlur',
      ],
    ),
    'image': const ShareComponentDefinition(
      builder: _buildImage,
      inspectorProperties: [
        'assetId',
        'fallbackAssetId',
        'fit',
        'imageAlignment',
        'clip',
        'opacity',
        'blur',
        'borderRadius',
        'borderWidth',
        'shadowBlur',
      ],
    ),
    'asset': const ShareComponentDefinition(
      builder: _buildImage,
      inspectorProperties: [
        'assetId',
        'fit',
        'imageAlignment',
        'opacity',
        'blur',
      ],
    ),
    'shape': const ShareComponentDefinition(
      builder: _buildShape,
      inspectorProperties: [
        'shape',
        'color',
        'gradientKind',
        'colors',
        'stops',
        'borderRadius',
        'borderWidth',
        'shadowBlur',
      ],
    ),
  };

  bool supports(String type) =>
      type == 'background' ||
      type == 'stickerWorkspace' ||
      _definitions.containsKey(type);

  ShareComponentDefinition? definition(String type) => _definitions[type];

  ShareLayerConfig decodeLayer(Map<String, dynamic> json) {
    final layer = ShareLayerConfig.fromJson(json);
    final definition = _definitions[layer.type];
    if (definition == null) {
      throw FormatException('No component registered for ${layer.type}');
    }
    definition.validator?.call(layer);
    return layer;
  }

  bool allowsInteraction(String type, String interaction) =>
      _definitions[type]?.interactions.contains(interaction) ??
      type == 'stickerWorkspace';

  Widget build(ShareComponentContext context) {
    final definition = _definitions[context.layer.type];
    if (definition == null) {
      return ColoredBox(
        color: const Color(0x22FF0000),
        child: Center(child: Text('Unsupported: ${context.layer.type}')),
      );
    }
    definition.validator?.call(context.layer);
    return definition.builder(context);
  }
}

final class GeneratedShareRenderer extends StatefulWidget {
  const GeneratedShareRenderer({
    required this.theme,
    required this.content,
    required this.value,
    super.key,
    this.controller,
    this.registry,
    this.imageResolver = defaultShareImageResolver,
    this.showSelection = true,
  });

  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final ShareEditorValue value;
  final ShareEditorController? controller;
  final ShareComponentRegistry? registry;
  final ShareImageProviderResolver imageResolver;
  final bool showSelection;

  @override
  State<GeneratedShareRenderer> createState() => _GeneratedShareRendererState();
}

final class _GeneratedShareRendererState extends State<GeneratedShareRenderer> {
  ShareEditorController? _ownedController;

  @override
  void initState() {
    super.initState();
    _createOwnedController();
  }

  @override
  void didUpdateWidget(GeneratedShareRenderer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.controller == null &&
        (oldWidget.controller != null ||
            oldWidget.theme != widget.theme ||
            oldWidget.content != widget.content ||
            oldWidget.value != widget.value)) {
      _ownedController?.dispose();
      _createOwnedController();
    } else if (widget.controller != null) {
      _ownedController?.dispose();
      _ownedController = null;
    }
  }

  void _createOwnedController() {
    if (widget.controller != null) return;
    _ownedController = ShareEditorController(
      theme: widget.theme,
      content: widget.content,
      initialValue: widget.value,
      entitlements: (_) => true,
    );
  }

  @override
  void dispose() {
    _ownedController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final effectiveController = widget.controller ?? _ownedController!;
    Widget buildBody() => AspectRatio(
      aspectRatio: widget.theme.canvas.width / widget.theme.canvas.height,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final scale = constraints.maxWidth / widget.theme.canvas.width;
          return ClipRect(
            child: Stack(
              fit: StackFit.expand,
              children: [
                for (final layer in widget.theme.layers)
                  _ConfiguredLayer(
                    key: ValueKey('share_layer_${layer.id}'),
                    interactionKey: ValueKey(
                      layer.id == 'headline'
                          ? 'story_canvas_headline'
                          : layer.id == 'secondary'
                          ? 'story_canvas_dare'
                          : 'share_layer_${layer.id}',
                    ),
                    controller: effectiveController,
                    layerId: layer.id,
                    scale: scale,
                    registry: widget.registry ?? ShareComponentRegistry(),
                    imageResolver: widget.imageResolver,
                    editable: widget.controller != null,
                    showSelection: widget.showSelection,
                  ),
              ],
            ),
          );
        },
      ),
    );
    return widget.controller == null
        ? buildBody()
        : AnimatedBuilder(
          animation: widget.controller!,
          builder: (_, __) => buildBody(),
        );
  }
}

ImageProvider<Object>? defaultShareImageResolver(ShareImageValue image) =>
    switch (image.source) {
      ShareImageSource.asset => AssetImage(image.path!),
      ShareImageSource.memory => MemoryImage(image.bytes!),
      ShareImageSource.network => NetworkImage(image.path!),
      ShareImageSource.file => null,
    };

final class _ConfiguredLayer extends StatelessWidget {
  const _ConfiguredLayer({
    required this.controller,
    required this.layerId,
    required this.scale,
    required this.registry,
    required this.imageResolver,
    required this.editable,
    required this.showSelection,
    required this.interactionKey,
    super.key,
  });

  final ShareEditorController controller;
  final String layerId;
  final double scale;
  final ShareComponentRegistry registry;
  final ShareImageProviderResolver imageResolver;
  final bool editable;
  final bool showSelection;
  final Key interactionKey;

  @override
  Widget build(BuildContext context) {
    final layer = controller.effectiveLayer(layerId);
    final access = controller.accessState(layer.access);
    if (!layer.visible || access == ShareAccessState.hidden) {
      return const SizedBox.shrink();
    }
    final transform = controller.effectiveTransform(layerId);
    final style = controller.effectiveStyle(layerId);
    final selected = controller.selectedLayerId == layerId;
    final child = switch (layer.type) {
      'background' => _ShareBackground(
        controller: controller,
        imageResolver: imageResolver,
      ),
      'stickerWorkspace' => _StickerWorkspace(
        controller: controller,
        layer: layer,
        imageResolver: imageResolver,
        editable: editable,
      ),
      _ => registry.build(
        ShareComponentContext(
          context: context,
          theme: controller.theme,
          layer: layer,
          value: controller.layerValue(layerId),
          style: style,
          scale: scale,
          imageResolver: imageResolver,
        ),
      ),
    };
    if (layer.type == 'stickerWorkspace') {
      return Positioned(
        left: transform.x * scale,
        top: transform.y * scale,
        width: transform.width * scale,
        height: transform.height * scale,
        child: child,
      );
    }
    return Positioned(
      left: transform.x * scale,
      top: transform.y * scale,
      width: transform.width * scale,
      height: transform.height * scale,
      child: Transform.rotate(
        angle: transform.rotation,
        child: GestureDetector(
          key: interactionKey,
          behavior:
              layer.type == 'stickerWorkspace'
                  ? HitTestBehavior.deferToChild
                  : HitTestBehavior.translucent,
          onTap:
              editable &&
                      layer.type != 'stickerWorkspace' &&
                      registry.allowsInteraction(layer.type, 'select')
                  ? () => controller.selectLayer(layerId)
                  : null,
          onPanUpdate:
              editable &&
                      layer.type != 'stickerWorkspace' &&
                      registry.allowsInteraction(layer.type, 'move') &&
                      controller.controlAccess(layerId, 'move') ==
                          ShareAccessState.available
                  ? (details) => controller.updateLayerTransform(
                    layerId,
                    x: transform.x + details.delta.dx / scale,
                    y: transform.y + details.delta.dy / scale,
                  )
                  : null,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border:
                        editable && showSelection && selected
                            ? Border.all(
                              color: const Color(0xFFFFD84A),
                              width: 2,
                            )
                            : null,
                  ),
                  child: child,
                ),
              ),
              if (editable &&
                  showSelection &&
                  selected &&
                  registry.allowsInteraction(layer.type, 'resize') &&
                  controller.controlAccess(layerId, 'resize') ==
                      ShareAccessState.available)
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: GestureDetector(
                    key: ValueKey('share_resize_$layerId'),
                    behavior: HitTestBehavior.opaque,
                    onPanUpdate:
                        (details) => controller.updateLayerTransform(
                          layerId,
                          width: transform.width + details.delta.dx / scale,
                          height: transform.height + details.delta.dy / scale,
                        ),
                    child: const _LayerHandle(icon: Icons.open_in_full_rounded),
                  ),
                ),
              if (editable &&
                  showSelection &&
                  selected &&
                  registry.allowsInteraction(layer.type, 'rotate') &&
                  controller.controlAccess(layerId, 'rotate') ==
                      ShareAccessState.available)
                Positioned(
                  right: 0,
                  top: 0,
                  child: GestureDetector(
                    key: ValueKey('share_rotate_$layerId'),
                    behavior: HitTestBehavior.opaque,
                    onPanUpdate:
                        (details) => controller.updateLayerTransform(
                          layerId,
                          rotation:
                              transform.rotation + details.delta.dx * 0.012,
                        ),
                    child: const _LayerHandle(icon: Icons.rotate_right_rounded),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

final class _LayerHandle extends StatelessWidget {
  const _LayerHandle({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) => Material(
    color: Colors.white,
    shape: const CircleBorder(),
    child: Padding(
      padding: const EdgeInsets.all(4),
      child: Icon(icon, size: 16, color: Colors.black),
    ),
  );
}

Widget _buildText(ShareComponentContext data) {
  final text = '${data.value ?? ''}';
  final style = data.style;
  final color = shareColor(style['color'], fallback: Colors.white);
  final fontSize = _number(style['fontSize'], 32) * data.scale;
  final fontWeight = FontWeight.values.firstWhere(
    (item) => item.value == _integer(style['fontWeight'], 700),
    orElse: () => FontWeight.w700,
  );
  final shadows = <Shadow>[];
  if (_number(style['shadowBlur'], 0) > 0 ||
      _number(style['shadowX'], 0) != 0 ||
      _number(style['shadowY'], 0) != 0) {
    shadows.add(
      Shadow(
        color: shareColor(style['shadowColor'], fallback: Colors.black54),
        blurRadius: _number(style['shadowBlur'], 0) * data.scale,
        offset: Offset(
          _number(style['shadowX'], 0) * data.scale,
          _number(style['shadowY'], 0) * data.scale,
        ),
      ),
    );
  }
  final textStyle = TextStyle(
    color: color,
    fontFamily: style['fontFamily'] as String?,
    fontSize: fontSize,
    fontWeight: fontWeight,
    fontStyle: style['italic'] == true ? FontStyle.italic : FontStyle.normal,
    height: _number(style['lineHeight'], 1.08),
    letterSpacing: _number(style['letterSpacing'], 0) * data.scale,
    shadows: shadows,
  );
  final alignment = shareTextAlign(style['textAlign']);
  final maximum = _integer(style['maxLines'], 5);
  Widget result;
  if (style['autoSize'] == true) {
    result = LayoutBuilder(
      builder: (context, constraints) {
        final minSize = _number(style['minFontSize'], 12) * data.scale;
        var size = fontSize;
        for (var candidate = fontSize; candidate >= minSize; candidate -= 1) {
          final painter = TextPainter(
            text: TextSpan(
              text: text,
              style: textStyle.copyWith(fontSize: candidate),
            ),
            textAlign: alignment,
            textDirection: Directionality.of(context),
            maxLines: maximum,
          )..layout(maxWidth: constraints.maxWidth);
          size = candidate;
          if (!painter.didExceedMaxLines &&
              painter.height <= constraints.maxHeight) {
            break;
          }
        }
        return Text(
          text,
          textAlign: alignment,
          maxLines: maximum,
          overflow: shareTextOverflow(style['overflow']),
          style: textStyle.copyWith(fontSize: size),
        );
      },
    );
  } else {
    result = Text(
      text,
      textAlign: alignment,
      maxLines: maximum,
      overflow: shareTextOverflow(style['overflow']),
      style: textStyle,
    );
  }
  final strokeWidth = _number(style['strokeWidth'], 0) * data.scale;
  if (strokeWidth > 0) {
    result = Stack(
      fit: StackFit.passthrough,
      children: [
        Text(
          text,
          textAlign: alignment,
          maxLines: maximum,
          overflow: shareTextOverflow(style['overflow']),
          style: textStyle.copyWith(
            foreground:
                Paint()
                  ..style = PaintingStyle.stroke
                  ..strokeWidth = strokeWidth
                  ..color = shareColor(
                    style['strokeColor'],
                    fallback: Colors.black,
                  ),
          ),
        ),
        result,
      ],
    );
  }
  return Container(
    alignment: shareAlignment(style['alignment'], fallback: Alignment.center),
    padding: EdgeInsets.all(_number(style['padding'], 0) * data.scale),
    decoration: BoxDecoration(
      color:
          style['backgroundColor'] == null
              ? null
              : shareColor(style['backgroundColor']),
      borderRadius: BorderRadius.circular(
        _number(style['borderRadius'], 0) * data.scale,
      ),
      border:
          _number(style['borderWidth'], 0) <= 0
              ? null
              : Border.all(
                color: shareColor(style['borderColor'], fallback: Colors.white),
                width: _number(style['borderWidth'], 0) * data.scale,
              ),
    ),
    child: result,
  );
}

Widget _buildImage(ShareComponentContext data) {
  final style = data.style;
  ShareImageValue? value;
  if (data.value is ShareImageValue) value = data.value as ShareImageValue;
  final assetId = style['assetId'] as String?;
  if (value == null && assetId != null) {
    value = _assetImageValue(data.theme.asset(assetId));
  }
  final provider = value == null ? null : data.imageResolver(value);
  final fallbackAssetId = style['fallbackAssetId'] as String?;
  final fallbackValue =
      fallbackAssetId == null
          ? null
          : _assetImageValue(data.theme.asset(fallbackAssetId));
  final fallbackProvider =
      fallbackValue == null ? null : data.imageResolver(fallbackValue);
  Widget fallback() =>
      fallbackProvider == null
          ? const ColoredBox(
            color: Color(0x22111122),
            child: Center(child: Icon(Icons.broken_image_outlined)),
          )
          : Image(
            image: fallbackProvider,
            fit: shareBoxFit(style['fit']),
            alignment: shareAlignment(style['imageAlignment']),
          );
  Widget image =
      provider == null
          ? fallback()
          : Image(
            image: provider,
            fit: shareBoxFit(style['fit']),
            alignment: shareAlignment(style['imageAlignment']),
            opacity: AlwaysStoppedAnimation(_number(style['opacity'], 1)),
            errorBuilder: (_, __, ___) => fallback(),
          );
  final blur = _number(style['blur'], 0) * data.scale;
  if (blur > 0) {
    image = ImageFiltered(
      imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
      child: image,
    );
  }
  final clip = style['clip'] as String? ?? 'rounded';
  final radius = _number(style['borderRadius'], 0) * data.scale;
  image = switch (clip) {
    'oval' => ClipOval(child: image),
    'none' => image,
    _ => ClipRRect(borderRadius: BorderRadius.circular(radius), child: image),
  };
  final borderWidth = _number(style['borderWidth'], 0) * data.scale;
  return DecoratedBox(
    decoration: BoxDecoration(
      shape: clip == 'oval' ? BoxShape.circle : BoxShape.rectangle,
      borderRadius: clip == 'oval' ? null : BorderRadius.circular(radius),
      border:
          borderWidth <= 0
              ? null
              : Border.all(
                color: shareColor(style['borderColor'], fallback: Colors.white),
                width: borderWidth,
              ),
      boxShadow:
          _number(style['shadowBlur'], 0) <= 0
              ? null
              : [
                BoxShadow(
                  color: shareColor(
                    style['shadowColor'],
                    fallback: Colors.black45,
                  ),
                  blurRadius: _number(style['shadowBlur'], 0) * data.scale,
                  offset: Offset(
                    _number(style['shadowX'], 0) * data.scale,
                    _number(style['shadowY'], 0) * data.scale,
                  ),
                ),
              ],
    ),
    child: image,
  );
}

Widget _buildShape(ShareComponentContext data) {
  final style = data.style;
  final gradient = _gradientFromProperties(style);
  return DecoratedBox(
    decoration: BoxDecoration(
      color:
          gradient == null
              ? shareColor(style['color'], fallback: Colors.white)
              : null,
      gradient: gradient,
      shape: style['shape'] == 'oval' ? BoxShape.circle : BoxShape.rectangle,
      borderRadius:
          style['shape'] == 'oval'
              ? null
              : BorderRadius.circular(
                _number(style['borderRadius'], 0) * data.scale,
              ),
      border:
          _number(style['borderWidth'], 0) <= 0
              ? null
              : Border.all(
                color: shareColor(style['borderColor'], fallback: Colors.white),
                width: _number(style['borderWidth'], 0) * data.scale,
              ),
      boxShadow:
          _number(style['shadowBlur'], 0) <= 0
              ? null
              : [
                BoxShadow(
                  color: shareColor(
                    style['shadowColor'],
                    fallback: Colors.black45,
                  ),
                  blurRadius: _number(style['shadowBlur'], 0) * data.scale,
                  offset: Offset(
                    _number(style['shadowX'], 0) * data.scale,
                    _number(style['shadowY'], 0) * data.scale,
                  ),
                ),
              ],
    ),
  );
}

final class _ShareBackground extends StatelessWidget {
  const _ShareBackground({
    required this.controller,
    required this.imageResolver,
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;

  @override
  Widget build(BuildContext context) {
    final id =
        controller.value.backgroundId ?? controller.theme.defaultBackgroundId;
    final background = controller.theme.background(id);
    final properties = background.properties;
    if (background.kind == 'image') {
      ShareImageValue? image;
      if (properties['binding'] is String) {
        final resolved = controller.content.resolve(
          properties['binding'] as String,
        );
        if (resolved is ShareImageValue) image = resolved;
      }
      final assetId = properties['assetId'] as String?;
      if (image == null && assetId != null) {
        image = _assetImageValue(controller.theme.asset(assetId));
      }
      final provider = image == null ? null : imageResolver(image);
      final fallbackAssetId = properties['fallbackAssetId'] as String?;
      final fallbackValue =
          fallbackAssetId == null
              ? null
              : _assetImageValue(controller.theme.asset(fallbackAssetId));
      final fallbackProvider =
          fallbackValue == null ? null : imageResolver(fallbackValue);
      Widget fallback() =>
          fallbackProvider == null
              ? const ColoredBox(color: Color(0xFF141827))
              : Image(
                image: fallbackProvider,
                fit: shareBoxFit(properties['fit']),
                alignment: shareAlignment(properties['alignment']),
              );
      Widget result =
          provider == null
              ? fallback()
              : Image(
                image: provider,
                fit: shareBoxFit(properties['fit']),
                alignment: shareAlignment(properties['alignment']),
                errorBuilder: (_, __, ___) => fallback(),
              );
      final blur = _number(properties['blur'], 0);
      if (blur > 0) {
        result = ImageFiltered(
          imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: Transform.scale(scale: 1.04, child: result),
        );
      }
      final overlay = properties['overlayColor'];
      if (overlay != null) {
        result = Stack(
          fit: StackFit.expand,
          children: [result, ColoredBox(color: shareColor(overlay))],
        );
      }
      return result;
    }
    if (background.kind == 'solid') {
      return ColoredBox(
        color: shareColor(
          properties['color'],
          fallback: const Color(0xFF141827),
        ),
      );
    }
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: _gradientFromProperties(properties, kind: background.kind),
      ),
    );
  }
}

final class _StickerWorkspace extends StatelessWidget {
  const _StickerWorkspace({
    required this.controller,
    required this.layer,
    required this.imageResolver,
    required this.editable,
  });

  final ShareEditorController controller;
  final ShareLayerConfig layer;
  final ShareImageProviderResolver imageResolver;
  final bool editable;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder:
        (context, constraints) => Stack(
          clipBehavior: Clip.none,
          children: [
            for (final sticker in controller.value.stickers)
              _StickerLayer(
                controller: controller,
                sticker: sticker,
                workspaceSize: constraints.biggest,
                imageResolver: imageResolver,
                editable: editable,
              ),
          ],
        ),
  );
}

final class _StickerLayer extends StatefulWidget {
  const _StickerLayer({
    required this.controller,
    required this.sticker,
    required this.workspaceSize,
    required this.imageResolver,
    required this.editable,
  });

  final ShareEditorController controller;
  final ShareStickerValue sticker;
  final Size workspaceSize;
  final ShareImageProviderResolver imageResolver;
  final bool editable;

  @override
  State<_StickerLayer> createState() => _StickerLayerState();
}

final class _StickerLayerState extends State<_StickerLayer> {
  late ShareStickerValue _start;

  @override
  Widget build(BuildContext context) {
    final config = widget.controller.theme.sticker(widget.sticker.stickerId);
    final asset = widget.controller.theme.asset(config.assetId);
    final image =
        asset.embeddedBytes == null
            ? ShareImageValue.asset(asset.path!)
            : ShareImageValue.memory(
              asset.embeddedBytes!,
              mimeType: asset.mimeType,
            );
    final provider = widget.imageResolver(image);
    final side = widget.workspaceSize.width * widget.sticker.scale;
    final selected =
        widget.controller.selectedStickerId == widget.sticker.instanceId;
    return Positioned(
      left: widget.workspaceSize.width * widget.sticker.centerX - side / 2,
      top: widget.workspaceSize.height * widget.sticker.centerY - side / 2,
      width: side,
      height: side,
      child: Transform.rotate(
        angle: widget.sticker.rotation,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned.fill(
              child: GestureDetector(
                key: ValueKey(
                  'story_canvas_sticker_${widget.sticker.instanceId}',
                ),
                behavior: HitTestBehavior.opaque,
                onTap:
                    widget.editable
                        ? () => widget.controller.selectSticker(
                          widget.sticker.instanceId,
                        )
                        : null,
                onScaleStart:
                    widget.editable
                        ? (_) {
                          _start = widget.sticker;
                          widget.controller.selectSticker(
                            widget.sticker.instanceId,
                          );
                        }
                        : null,
                onScaleUpdate:
                    widget.editable
                        ? (details) => widget.controller.updateSticker(
                          widget.sticker.instanceId,
                          centerX:
                              widget.sticker.centerX +
                              details.focalPointDelta.dx /
                                  widget.workspaceSize.width,
                          centerY:
                              widget.sticker.centerY +
                              details.focalPointDelta.dy /
                                  widget.workspaceSize.height,
                          scale: _start.scale * details.scale,
                          rotation: _start.rotation + details.rotation,
                        )
                        : null,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border:
                        widget.editable && selected
                            ? Border.all(color: Colors.white, width: 2)
                            : null,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child:
                      provider == null
                          ? const Icon(Icons.broken_image_outlined)
                          : Image(image: provider, fit: BoxFit.contain),
                ),
              ),
            ),
            if (widget.editable && selected && config.canDelete)
              Positioned(
                left: 0,
                top: 0,
                child: Material(
                  color: Colors.white,
                  shape: const CircleBorder(),
                  child: InkWell(
                    key: const ValueKey('story_delete_sticker'),
                    customBorder: const CircleBorder(),
                    onTap:
                        () => widget.controller.removeSticker(
                          widget.sticker.instanceId,
                        ),
                    child: const Padding(
                      padding: EdgeInsets.all(4),
                      child: Icon(
                        Icons.close_rounded,
                        size: 16,
                        color: Colors.black,
                      ),
                    ),
                  ),
                ),
              ),
            if (widget.editable && selected && config.canResize)
              Positioned(
                right: 0,
                bottom: 0,
                child: GestureDetector(
                  key: const ValueKey('story_transform_handle'),
                  behavior: HitTestBehavior.opaque,
                  onPanUpdate:
                      (details) => widget.controller.updateSticker(
                        widget.sticker.instanceId,
                        scale:
                            widget.sticker.scale +
                            details.delta.dx / widget.workspaceSize.width,
                        rotation:
                            widget.sticker.rotation + details.delta.dy * 0.012,
                      ),
                  child: const Material(
                    color: Colors.white,
                    shape: CircleBorder(),
                    child: Padding(
                      padding: EdgeInsets.all(4),
                      child: Icon(
                        Icons.sync_rounded,
                        size: 16,
                        color: Colors.black,
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
}

Gradient? _gradientFromProperties(
  Map<String, Object?> properties, {
  String? kind,
}) {
  final gradientKind = kind ?? properties['gradientKind'] as String?;
  if (gradientKind == null) return null;
  final opacity = _number(properties['opacity'], 1).clamp(0.0, 1.0);
  final colors =
      (properties['colors'] as List<dynamic>? ??
              const ['#FFFFFFFF', '#FF000000'])
          .map(shareColor)
          .map((color) => color.withValues(alpha: color.a * opacity))
          .toList();
  final rawStops = properties['stops'] as List<dynamic>?;
  final stops = rawStops?.map((item) => (item as num).toDouble()).toList();
  final tileMode = switch (properties['tileMode']) {
    'repeat' => TileMode.repeated,
    'mirror' => TileMode.mirror,
    'decal' => TileMode.decal,
    _ => TileMode.clamp,
  };
  return switch (gradientKind) {
    'radial' => RadialGradient(
      center: shareAlignment(properties['center']),
      focal:
          properties['focalX'] == null
              ? null
              : Alignment(
                _number(properties['focalX'], 0),
                _number(properties['focalY'], 0),
              ),
      radius: _number(properties['radius'], 0.5),
      focalRadius: _number(properties['focalRadius'], 0),
      colors: colors,
      stops: stops,
      tileMode: tileMode,
      transform: GradientRotation(_number(properties['rotation'], 0)),
    ),
    'sweep' => SweepGradient(
      center: shareAlignment(properties['center']),
      startAngle: _number(properties['startAngle'], 0),
      endAngle: _number(properties['endAngle'], math.pi * 2),
      colors: colors,
      stops: stops,
      tileMode: tileMode,
      transform: GradientRotation(_number(properties['rotation'], 0)),
    ),
    _ => LinearGradient(
      begin: shareAlignment(properties['begin'], fallback: Alignment.topLeft),
      end: shareAlignment(properties['end'], fallback: Alignment.bottomRight),
      colors: colors,
      stops: stops,
      tileMode: tileMode,
      transform: GradientRotation(_number(properties['rotation'], 0)),
    ),
  };
}

ShareImageValue _assetImageValue(ShareAssetConfig asset) =>
    asset.embeddedBytes == null
        ? ShareImageValue.asset(asset.path!)
        : ShareImageValue.memory(
          asset.embeddedBytes!,
          mimeType: asset.mimeType,
        );

Color shareColor(Object? value, {Color fallback = Colors.transparent}) {
  if (value is int) return Color(value);
  if (value is String) {
    final clean = value.replaceFirst('#', '');
    final normalized = clean.length == 6 ? 'FF$clean' : clean;
    final parsed = int.tryParse(normalized, radix: 16);
    if (parsed != null) return Color(parsed);
  }
  return fallback;
}

Alignment shareAlignment(
  Object? value, {
  Alignment fallback = Alignment.center,
}) {
  if (value is List<dynamic> && value.length == 2) {
    return Alignment(
      (value[0] as num).toDouble(),
      (value[1] as num).toDouble(),
    );
  }
  return switch (value) {
    'topLeft' => Alignment.topLeft,
    'topCenter' => Alignment.topCenter,
    'topRight' => Alignment.topRight,
    'centerLeft' => Alignment.centerLeft,
    'centerRight' => Alignment.centerRight,
    'bottomLeft' => Alignment.bottomLeft,
    'bottomCenter' => Alignment.bottomCenter,
    'bottomRight' => Alignment.bottomRight,
    _ => fallback,
  };
}

TextAlign shareTextAlign(Object? value) => switch (value) {
  'left' => TextAlign.left,
  'right' => TextAlign.right,
  'start' => TextAlign.start,
  'end' => TextAlign.end,
  'justify' => TextAlign.justify,
  _ => TextAlign.center,
};

TextOverflow shareTextOverflow(Object? value) => switch (value) {
  'clip' => TextOverflow.clip,
  'fade' => TextOverflow.fade,
  'visible' => TextOverflow.visible,
  _ => TextOverflow.ellipsis,
};

BoxFit shareBoxFit(Object? value) => switch (value) {
  'contain' => BoxFit.contain,
  'fill' => BoxFit.fill,
  'fitWidth' => BoxFit.fitWidth,
  'fitHeight' => BoxFit.fitHeight,
  'none' => BoxFit.none,
  'scaleDown' => BoxFit.scaleDown,
  _ => BoxFit.cover,
};

double _number(Object? value, double fallback) =>
    value is num ? value.toDouble() : fallback;

int _integer(Object? value, int fallback) =>
    value is num ? value.toInt() : fallback;
