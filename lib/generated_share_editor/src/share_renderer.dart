import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/foundation.dart';
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
    this.editBackground = false,
    this.showAuthoringGuides = false,
    this.interactionEnabled = true,
    this.liveLayerId,
    this.liveLayerDraft,
    this.liveStickerDraft,
    this.liveBackgroundTreatmentDraft,
    this.liveBackgroundDraft,
    this.isolateRepaints = false,
  });

  final ShareThemeConfig theme;
  final ShareEditorContent content;
  final ShareEditorValue value;
  final ShareEditorController? controller;
  final ShareComponentRegistry? registry;
  final ShareImageProviderResolver imageResolver;
  final bool showSelection;
  final bool editBackground;
  final bool showAuthoringGuides;
  final bool interactionEnabled;
  final String? liveLayerId;
  final ValueListenable<ShareLayerConfig?>? liveLayerDraft;
  final ValueListenable<ShareStickerValue?>? liveStickerDraft;
  final ValueListenable<ShareBackgroundEdit?>? liveBackgroundTreatmentDraft;
  final ValueListenable<ShareBackgroundConfig?>? liveBackgroundDraft;
  final bool isolateRepaints;

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
          return ClipRRect(
            key: const ValueKey('generated_share_canvas_clip'),
            borderRadius: BorderRadius.circular(
              widget.theme.canvas.cornerRadius * scale,
            ),
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
                    editable:
                        widget.controller != null && widget.interactionEnabled,
                    showSelection: widget.showSelection,
                    editBackground: widget.editBackground,
                    liveLayerDraft:
                        layer.id == widget.liveLayerId
                            ? widget.liveLayerDraft
                            : null,
                    liveStickerDraft:
                        layer.type == 'stickerWorkspace'
                            ? widget.liveStickerDraft
                            : null,
                    liveBackgroundTreatmentDraft:
                        layer.type == 'background'
                            ? widget.liveBackgroundTreatmentDraft
                            : null,
                    liveBackgroundDraft:
                        layer.type == 'background'
                            ? widget.liveBackgroundDraft
                            : null,
                    isolateRepaints: widget.isolateRepaints,
                  ),
                if (widget.showAuthoringGuides)
                  Positioned.fill(
                    child: IgnorePointer(
                      child: RepaintBoundary(
                        child: CustomPaint(
                          key: const ValueKey('share_safe_zone_overlay'),
                          painter: _SafeZonePainter(
                            canvas: widget.theme.canvas,
                            zones: effectiveController.activeTemplate.safeZones,
                          ),
                        ),
                      ),
                    ),
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

final class _SafeZonePainter extends CustomPainter {
  const _SafeZonePainter({required this.canvas, required this.zones});

  final ShareCanvasConfig canvas;
  final List<ShareSafeZoneConfig> zones;

  @override
  void paint(Canvas target, Size size) {
    final scaleX = size.width / canvas.width;
    final scaleY = size.height / canvas.height;
    for (final zone in zones) {
      final color = switch (zone.kind) {
        ShareSafeZoneKind.instagramTopDanger ||
        ShareSafeZoneKind.instagramBottomDanger => const Color(0xFFFF5D73),
        ShareSafeZoneKind.recommendedLink => const Color(0xFF61DAFB),
        ShareSafeZoneKind.protectedSubject => const Color(0xFFFFD84A),
        ShareSafeZoneKind.brandSafe => const Color(0xFF66E3A4),
      };
      final rect = Rect.fromLTWH(
        zone.rect.x * scaleX,
        zone.rect.y * scaleY,
        zone.rect.width * scaleX,
        zone.rect.height * scaleY,
      );
      target.drawRect(
        rect,
        Paint()
          ..color = color.withValues(alpha: 0.08)
          ..style = PaintingStyle.fill,
      );
      target.drawRect(
        rect,
        Paint()
          ..color = color.withValues(alpha: 0.9)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2,
      );
      final label = TextPainter(
        text: TextSpan(
          text: zone.label,
          style: TextStyle(
            color: color,
            fontSize: math.max(8, 9 * scaleX),
            fontWeight: FontWeight.w700,
            backgroundColor: const Color(0xCC111827),
          ),
        ),
        maxLines: 1,
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: math.max(1, rect.width - 6));
      label.paint(target, Offset(rect.left + 3, rect.top + 2));
    }
  }

  @override
  bool shouldRepaint(covariant _SafeZonePainter oldDelegate) =>
      oldDelegate.canvas != canvas || oldDelegate.zones != zones;
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
    required this.editBackground,
    this.liveLayerDraft,
    this.liveStickerDraft,
    this.liveBackgroundTreatmentDraft,
    this.liveBackgroundDraft,
    this.isolateRepaints = false,
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
  final bool editBackground;
  final ValueListenable<ShareLayerConfig?>? liveLayerDraft;
  final ValueListenable<ShareStickerValue?>? liveStickerDraft;
  final ValueListenable<ShareBackgroundEdit?>? liveBackgroundTreatmentDraft;
  final ValueListenable<ShareBackgroundConfig?>? liveBackgroundDraft;
  final bool isolateRepaints;

  @override
  Widget build(BuildContext context) {
    Widget buildLayer(
      ShareLayerConfig? liveLayer,
      ShareStickerValue? liveSticker,
      ShareBackgroundEdit? liveBackgroundTreatment,
      ShareBackgroundConfig? liveBackground,
    ) {
      final effectiveLayer = controller.effectiveLayer(layerId);
      final layer = liveLayer?.id == layerId ? liveLayer! : effectiveLayer;
      final access = controller.accessState(layer.access);
      if (!layer.visible || access == ShareAccessState.hidden) {
        return const SizedBox.shrink();
      }
      final transform =
          liveLayer?.id == layerId
              ? liveLayer!.transform
              : controller.effectiveTransform(layerId);
      final style =
          liveLayer?.id == layerId
              ? liveLayer!.style
              : controller.effectiveStyle(layerId);
      final selected = controller.selectedLayerId == layerId;
      Widget isolate(Widget child) =>
          isolateRepaints ? RepaintBoundary(child: child) : child;
      final child = switch (layer.type) {
        'background' => _ShareBackground(
          controller: controller,
          imageResolver: imageResolver,
          editable: editable && editBackground,
          backgroundOverride: liveBackground,
          editOverride: liveBackgroundTreatment,
        ),
        'stickerWorkspace' => _StickerWorkspace(
          controller: controller,
          layer: layer,
          imageResolver: imageResolver,
          editable: editable,
          liveSticker: liveSticker,
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
          child: isolate(child),
        );
      }
      return Positioned(
        left: transform.x * scale,
        top: transform.y * scale,
        width: transform.width * scale,
        height: transform.height * scale,
        child: isolate(
          Transform.rotate(
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
                              height:
                                  transform.height + details.delta.dy / scale,
                            ),
                        child: const _LayerHandle(
                          icon: Icons.open_in_full_rounded,
                        ),
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
                        child: const _LayerHandle(
                          icon: Icons.rotate_right_rounded,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    Widget withBackground(
      ShareLayerConfig? liveLayer,
      ShareStickerValue? liveSticker,
    ) {
      Widget withConfig(ShareBackgroundEdit? treatment) {
        final backgroundListenable = liveBackgroundDraft;
        if (backgroundListenable == null) {
          return buildLayer(liveLayer, liveSticker, treatment, null);
        }
        return ValueListenableBuilder<ShareBackgroundConfig?>(
          valueListenable: backgroundListenable,
          builder:
              (_, background, __) =>
                  buildLayer(liveLayer, liveSticker, treatment, background),
        );
      }

      final treatmentListenable = liveBackgroundTreatmentDraft;
      if (treatmentListenable == null) return withConfig(null);
      return ValueListenableBuilder<ShareBackgroundEdit?>(
        valueListenable: treatmentListenable,
        builder: (_, treatment, __) => withConfig(treatment),
      );
    }

    Widget withSticker(ShareLayerConfig? liveLayer) {
      final listenable = liveStickerDraft;
      if (listenable == null) return withBackground(liveLayer, null);
      return ValueListenableBuilder<ShareStickerValue?>(
        valueListenable: listenable,
        builder: (_, liveSticker, __) => withBackground(liveLayer, liveSticker),
      );
    }

    final listenable = liveLayerDraft;
    if (listenable == null) return withSticker(null);
    return ValueListenableBuilder<ShareLayerConfig?>(
      valueListenable: listenable,
      builder: (_, liveLayer, __) => withSticker(liveLayer),
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

final class _ShareBackground extends StatefulWidget {
  const _ShareBackground({
    required this.controller,
    required this.imageResolver,
    required this.editable,
    this.backgroundOverride,
    this.editOverride,
  });

  final ShareEditorController controller;
  final ShareImageProviderResolver imageResolver;
  final bool editable;
  final ShareBackgroundConfig? backgroundOverride;
  final ShareBackgroundEdit? editOverride;

  @override
  State<_ShareBackground> createState() => _ShareBackgroundState();
}

final class _ShareBackgroundState extends State<_ShareBackground> {
  late ShareBackgroundEdit _gestureStart;

  @override
  Widget build(BuildContext context) {
    final id =
        widget.controller.value.backgroundId ??
        widget.controller.theme.defaultBackgroundId;
    final background =
        widget.backgroundOverride?.id == id
            ? widget.backgroundOverride!
            : widget.controller.theme.background(id);
    final properties = background.properties;
    final edit = widget.editOverride ?? widget.controller.value.backgroundEdit;
    Widget result;
    if (background.kind == 'image') {
      ShareImageValue? image = edit.image;
      if (properties['binding'] is String) {
        final resolved = widget.controller.content.resolve(
          properties['binding'] as String,
        );
        if (image == null && resolved is ShareImageValue) image = resolved;
      }
      final assetId = properties['assetId'] as String?;
      if (image == null && assetId != null) {
        image = _assetImageValue(widget.controller.theme.asset(assetId));
      }
      final provider = image == null ? null : widget.imageResolver(image);
      final fallbackAssetId = properties['fallbackAssetId'] as String?;
      final fallbackValue =
          fallbackAssetId == null
              ? null
              : _assetImageValue(
                widget.controller.theme.asset(fallbackAssetId),
              );
      final fallbackProvider =
          fallbackValue == null ? null : widget.imageResolver(fallbackValue);
      Widget fallback() =>
          fallbackProvider == null
              ? const ColoredBox(color: Color(0xFF141827))
              : Image(
                image: fallbackProvider,
                fit: shareBoxFit(properties['fit']),
                alignment: shareAlignment(properties['alignment']),
              );
      result =
          provider == null
              ? fallback()
              : Transform.scale(
                scale: edit.zoom,
                child: Image(
                  image: provider,
                  fit: shareBoxFit(properties['fit']),
                  alignment: Alignment(edit.alignmentX, edit.alignmentY),
                  opacity: AlwaysStoppedAnimation(edit.imageOpacity),
                  errorBuilder: (_, __, ___) => fallback(),
                ),
              );
      result = ColorFiltered(
        colorFilter: ColorFilter.matrix(_photoColorMatrix(edit)),
        child: result,
      );
      final blur = _number(properties['blur'], 0) + edit.blur;
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
    } else if (background.kind == 'solid') {
      result = ColoredBox(
        color: shareColor(
          properties['color'],
          fallback: const Color(0xFF141827),
        ),
      );
    } else {
      result = DecoratedBox(
        decoration: BoxDecoration(
          gradient: _gradientFromProperties(properties, kind: background.kind),
        ),
      );
    }

    result = Stack(
      fit: StackFit.expand,
      children: [
        result,
        if (edit.tintOpacity > 0)
          ColoredBox(
            color: shareColor(
              edit.tintColor,
            ).withValues(alpha: edit.tintOpacity),
          ),
        if (edit.overlayOpacity > 0)
          ColoredBox(
            color: shareColor(
              edit.overlayColor,
            ).withValues(alpha: edit.overlayOpacity),
          ),
        if (edit.texture != ShareBackgroundTexture.none &&
            edit.textureIntensity > 0)
          CustomPaint(
            key: const ValueKey('share_background_texture'),
            painter: _BackgroundTexturePainter(edit),
          ),
      ],
    );
    if (!widget.editable) return result;
    return LayoutBuilder(
      builder:
          (context, constraints) => GestureDetector(
            key: const ValueKey('share_background_crop_surface'),
            behavior: HitTestBehavior.opaque,
            onTap: () {
              widget.controller.selectLayer(null);
              widget.controller.selectSticker(null);
            },
            onDoubleTap:
                () => widget.controller.updateBackgroundCrop(
                  alignmentX: 0,
                  alignmentY: 0,
                  zoom: 1,
                ),
            onScaleStart:
                (_) => _gestureStart = widget.controller.value.backgroundEdit,
            onScaleUpdate: (details) {
              final width = math.max(1, constraints.maxWidth);
              final height = math.max(1, constraints.maxHeight);
              final current = widget.controller.value.backgroundEdit;
              widget.controller.updateBackgroundCrop(
                alignmentX:
                    current.alignmentX + details.focalPointDelta.dx * 2 / width,
                alignmentY:
                    current.alignmentY +
                    details.focalPointDelta.dy * 2 / height,
                zoom: _gestureStart.zoom * details.scale,
              );
            },
            child: result,
          ),
    );
  }
}

List<double> _photoColorMatrix(ShareBackgroundEdit edit) {
  final saturation = edit.saturation;
  final contrast = edit.contrast;
  final inverseSaturation = 1 - saturation;
  const red = 0.2126;
  const green = 0.7152;
  const blue = 0.0722;
  final offset = edit.brightness * 255 + 128 * (1 - contrast);
  return [
    (inverseSaturation * red + saturation) * contrast,
    inverseSaturation * green * contrast,
    inverseSaturation * blue * contrast,
    0,
    offset,
    inverseSaturation * red * contrast,
    (inverseSaturation * green + saturation) * contrast,
    inverseSaturation * blue * contrast,
    0,
    offset,
    inverseSaturation * red * contrast,
    inverseSaturation * green * contrast,
    (inverseSaturation * blue + saturation) * contrast,
    0,
    offset,
    0,
    0,
    0,
    1,
    0,
  ];
}

final class _BackgroundTexturePainter extends CustomPainter {
  const _BackgroundTexturePainter(this.edit);

  final ShareBackgroundEdit edit;

  @override
  void paint(Canvas canvas, Size size) {
    final primary = shareColor(
      edit.textureColor,
    ).withValues(alpha: edit.textureIntensity);
    final secondary = shareColor(
      edit.textureSecondaryColor,
    ).withValues(alpha: edit.textureIntensity);
    switch (edit.texture) {
      case ShareBackgroundTexture.none:
        return;
      case ShareBackgroundTexture.grain:
        final random = math.Random(7319);
        final count =
            (size.width * size.height / (34 * edit.textureScale)).round();
        final paint = Paint();
        for (var index = 0; index < count; index++) {
          paint.color = (index.isEven ? primary : secondary).withValues(
            alpha: edit.textureIntensity * (0.18 + random.nextDouble() * 0.5),
          );
          canvas.drawCircle(
            Offset(
              random.nextDouble() * size.width,
              random.nextDouble() * size.height,
            ),
            0.35 + random.nextDouble() * 0.9,
            paint,
          );
        }
        break;
      case ShareBackgroundTexture.stripes:
        final paint =
            Paint()
              ..color = primary
              ..strokeWidth = math.max(1, 1.4 * edit.textureScale);
        final gap = 7 * edit.textureScale;
        for (var y = 0.0; y <= size.height; y += gap) {
          canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
        }
        break;
      case ShareBackgroundTexture.blobs:
        final paint = Paint()..color = primary;
        final path =
            Path()
              ..moveTo(-size.width * 0.1, size.height * 0.14)
              ..quadraticBezierTo(
                size.width * 0.3,
                -size.height * 0.06,
                size.width * 0.74,
                size.height * 0.16,
              )
              ..quadraticBezierTo(
                size.width * 0.95,
                size.height * 0.27,
                size.width * 1.1,
                size.height * 0.09,
              )
              ..lineTo(size.width * 1.1, -20)
              ..lineTo(-20, -20)
              ..close();
        canvas.drawPath(path, paint);
        canvas.drawOval(
          Rect.fromCenter(
            center: Offset(size.width * 0.02, size.height * 0.82),
            width: size.width * 0.78,
            height: size.height * 0.3,
          ),
          Paint()..color = secondary,
        );
        break;
      case ShareBackgroundTexture.iridescent:
        final rect = Offset.zero & size;
        canvas.drawRect(
          rect,
          Paint()
            ..shader = LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                primary,
                secondary,
                const Color(
                  0xFFFF8BC2,
                ).withValues(alpha: edit.textureIntensity),
                const Color(
                  0xFFBFF7FF,
                ).withValues(alpha: edit.textureIntensity),
              ],
            ).createShader(rect),
        );
        break;
    }
  }

  @override
  bool shouldRepaint(_BackgroundTexturePainter oldDelegate) =>
      oldDelegate.edit.toJson().toString() != edit.toJson().toString();
}

final class _StickerWorkspace extends StatelessWidget {
  const _StickerWorkspace({
    required this.controller,
    required this.layer,
    required this.imageResolver,
    required this.editable,
    this.liveSticker,
  });

  final ShareEditorController controller;
  final ShareLayerConfig layer;
  final ShareImageProviderResolver imageResolver;
  final bool editable;
  final ShareStickerValue? liveSticker;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder:
        (context, constraints) => Stack(
          clipBehavior: Clip.none,
          children: [
            for (final sticker in controller.value.stickers)
              _StickerLayer(
                controller: controller,
                sticker:
                    liveSticker?.instanceId == sticker.instanceId
                        ? liveSticker!
                        : sticker,
                workspaceSize: constraints.biggest,
                imageResolver: imageResolver,
                editable: editable,
              ),
            for (final overlay in controller.value.overlays)
              _OverlayLayer(
                controller: controller,
                overlay: overlay,
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

final class _OverlayLayer extends StatefulWidget {
  const _OverlayLayer({
    required this.controller,
    required this.overlay,
    required this.workspaceSize,
    required this.imageResolver,
    required this.editable,
  });

  final ShareEditorController controller;
  final SharePlacedOverlayValue overlay;
  final Size workspaceSize;
  final ShareImageProviderResolver imageResolver;
  final bool editable;

  @override
  State<_OverlayLayer> createState() => _OverlayLayerState();
}

final class _OverlayLayerState extends State<_OverlayLayer> {
  late SharePlacedOverlayValue _start;

  @override
  Widget build(BuildContext context) {
    final provider = widget.imageResolver(widget.overlay.image);
    final side = widget.workspaceSize.width * widget.overlay.scale;
    final selected =
        widget.controller.selectedOverlayId == widget.overlay.instanceId;
    return Positioned(
      left: widget.workspaceSize.width * widget.overlay.centerX - side / 2,
      top: widget.workspaceSize.height * widget.overlay.centerY - side / 2,
      width: side,
      height: side,
      child: Transform.rotate(
        angle: widget.overlay.rotation,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned.fill(
              child: GestureDetector(
                key: ValueKey(
                  'story_canvas_overlay_${widget.overlay.instanceId}',
                ),
                behavior: HitTestBehavior.opaque,
                onTap:
                    widget.editable
                        ? () => widget.controller.selectOverlay(
                          widget.overlay.instanceId,
                        )
                        : null,
                onScaleStart:
                    widget.editable
                        ? (_) {
                          _start = widget.overlay;
                          widget.controller.selectOverlay(
                            widget.overlay.instanceId,
                          );
                        }
                        : null,
                onScaleUpdate:
                    widget.editable
                        ? (details) => widget.controller.updateOverlay(
                          widget.overlay.instanceId,
                          centerX:
                              widget.overlay.centerX +
                              details.focalPointDelta.dx /
                                  widget.workspaceSize.width,
                          centerY:
                              widget.overlay.centerY +
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
            if (widget.editable && selected)
              Positioned(
                left: 0,
                top: 0,
                child: Material(
                  color: Colors.white,
                  shape: const CircleBorder(),
                  child: InkWell(
                    key: const ValueKey('story_delete_overlay'),
                    customBorder: const CircleBorder(),
                    onTap:
                        () => widget.controller.removeOverlay(
                          widget.overlay.instanceId,
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
            if (widget.editable && selected)
              Positioned(
                right: 0,
                bottom: 0,
                child: GestureDetector(
                  key: const ValueKey('story_overlay_transform_handle'),
                  behavior: HitTestBehavior.opaque,
                  onPanUpdate:
                      (details) => widget.controller.updateOverlay(
                        widget.overlay.instanceId,
                        scale:
                            widget.overlay.scale +
                            details.delta.dx / widget.workspaceSize.width,
                        rotation:
                            widget.overlay.rotation + details.delta.dy * 0.012,
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
