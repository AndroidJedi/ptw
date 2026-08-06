import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/ptw_colors.dart';
import 'social_post_studio_controller.dart';
import 'studio_models.dart';

final class StoryPostCard extends StatelessWidget {
  const StoryPostCard({required this.draft, required this.catalog, super.key});

  static const logicalSize = Size(360, 640);
  static const exportSize = Size(1080, 1920);

  final SocialPostDraft draft;
  final MemeStickerCatalog catalog;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder:
        (context, constraints) => ClipRect(
          child: Stack(
            fit: StackFit.expand,
            children: [
              _StoryPostBase(draft: draft),
              for (final placement in draft.stickers)
                _StaticStickerLayer(
                  placement: placement,
                  definition: catalog.byId(placement.stickerId),
                  canvasSize: constraints.biggest,
                ),
            ],
          ),
        ),
  );
}

final class EditableStoryPostCard extends StatefulWidget {
  const EditableStoryPostCard({required this.controller, super.key});

  final SocialPostStudioController controller;

  @override
  State<EditableStoryPostCard> createState() => _EditableStoryPostCardState();
}

final class _EditableStoryPostCardState extends State<EditableStoryPostCard> {
  final _focusNode = FocusNode(debugLabel: 'Story canvas');
  final _canvasKey = GlobalKey();
  Offset? _transformCenterGlobal;
  double _transformStartDistance = 1;
  double _transformStartAngle = 0;
  double _transformStartScale = 0;
  double _transformStartRotation = 0;
  String? _transformInstanceId;

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) {
      final draft = widget.controller.draft;
      return KeyboardListener(
        focusNode: _focusNode,
        onKeyEvent: _handleKey,
        child: LayoutBuilder(
          builder:
              (context, constraints) => ClipRect(
                child: Stack(
                  key: _canvasKey,
                  fit: StackFit.expand,
                  children: [
                    Positioned.fill(
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: () {
                          _focusNode.requestFocus();
                          widget.controller.selectSticker(null);
                        },
                        child: _StoryPostBase(draft: draft),
                      ),
                    ),
                    for (final placement in draft.stickers)
                      _EditableStickerLayer(
                        placement: placement,
                        definition: widget.controller.catalog.byId(
                          placement.stickerId,
                        ),
                        canvasSize: constraints.biggest,
                        selected:
                            placement.instanceId ==
                            widget.controller.selectedStickerId,
                        onSelect: () {
                          _focusNode.requestFocus();
                          widget.controller.selectSticker(placement.instanceId);
                        },
                        onMove:
                            (delta) => widget.controller.updatePlacement(
                              placement.instanceId,
                              centerX:
                                  placement.centerX +
                                  delta.dx / StoryPostCard.logicalSize.width,
                              centerY:
                                  placement.centerY +
                                  delta.dy / StoryPostCard.logicalSize.height,
                            ),
                        onTransformStart:
                            (details) => _startTransform(details, placement),
                        onTransformUpdate: _updateTransform,
                      ),
                  ],
                ),
              ),
        ),
      );
    },
  );

  void _startTransform(DragStartDetails details, StickerPlacement placement) {
    final box = _canvasKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return;
    final centerGlobal = box.localToGlobal(
      Offset(
        placement.centerX * box.size.width,
        placement.centerY * box.size.height,
      ),
    );
    final vector = details.globalPosition - centerGlobal;
    _transformCenterGlobal = centerGlobal;
    _transformStartDistance = math.max(vector.distance, 1);
    _transformStartAngle = vector.direction;
    _transformStartScale = placement.scale;
    _transformStartRotation = placement.rotation;
    _transformInstanceId = placement.instanceId;
  }

  void _updateTransform(DragUpdateDetails details) {
    final center = _transformCenterGlobal;
    final instanceId = _transformInstanceId;
    if (center == null || instanceId == null) return;
    final vector = details.globalPosition - center;
    widget.controller.updatePlacement(
      instanceId,
      scale: _transformStartScale * (vector.distance / _transformStartDistance),
      rotation:
          _transformStartRotation + vector.direction - _transformStartAngle,
    );
  }

  void _handleKey(KeyEvent event) {
    if (event is! KeyDownEvent) return;
    if (event.logicalKey == LogicalKeyboardKey.delete ||
        event.logicalKey == LogicalKeyboardKey.backspace) {
      widget.controller.removeSelected();
      return;
    }
    final step = HardwareKeyboard.instance.isShiftPressed ? 0.025 : 0.006;
    if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
      widget.controller.nudgeSelected(dx: -step, dy: 0);
    } else if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
      widget.controller.nudgeSelected(dx: step, dy: 0);
    } else if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      widget.controller.nudgeSelected(dx: 0, dy: -step);
    } else if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      widget.controller.nudgeSelected(dx: 0, dy: step);
    } else if (event.logicalKey == LogicalKeyboardKey.escape) {
      widget.controller.selectSticker(null);
    }
  }
}

final class _StoryPostBase extends StatelessWidget {
  const _StoryPostBase({required this.draft});

  final SocialPostDraft draft;

  @override
  Widget build(BuildContext context) {
    final background = StudioBackgrounds.byId(draft.backgroundId);
    return LayoutBuilder(
      builder: (context, constraints) {
        final scale = constraints.maxWidth / StoryPostCard.logicalSize.width;
        return Stack(
          fit: StackFit.expand,
          children: [
            _Background(definition: background),
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  stops: const [0, 0.42, 1],
                  colors: [
                    PtwColors.ink.withValues(alpha: 0.16),
                    PtwColors.ink.withValues(alpha: 0.32),
                    PtwColors.ink.withValues(alpha: 0.7),
                  ],
                ),
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              top: 92 * scale,
              child: Center(
                child: Container(
                  width: 82 * scale,
                  height: 82 * scale,
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: PtwColors.textOnAccent,
                      width: 4 * scale,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: PtwColors.ink.withValues(alpha: 0.32),
                        blurRadius: 12 * scale,
                        offset: Offset(0, 5 * scale),
                      ),
                    ],
                  ),
                  child: _StudioImage(image: draft.avatar),
                ),
              ),
            ),
            Positioned(
              left: 32 * scale,
              right: 32 * scale,
              top: 214 * scale,
              height: 190 * scale,
              child: _AutoFitMessage(
                draft.message.trim().isEmpty
                    ? 'say something bold.'
                    : draft.message,
                scale: scale,
              ),
            ),
            Positioned(
              left: 24 * scale,
              bottom: 24 * scale,
              child: Text(
                'PTW',
                style: TextStyle(
                  color: PtwColors.textOnAccent,
                  fontFamily: 'PtwLilitaOne',
                  fontSize: 24 * scale,
                  height: 1,
                  letterSpacing: 0.8 * scale,
                  shadows: [
                    Shadow(
                      color: PtwColors.ink,
                      offset: Offset(2 * scale, 2 * scale),
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              right: 24 * scale,
              bottom: 25 * scale,
              child: Text(
                'PROVE THEM WRONG',
                style: TextStyle(
                  color: PtwColors.textOnAccent.withValues(alpha: 0.82),
                  fontFamily: 'PtwRoboto',
                  fontSize: 8.5 * scale,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.15 * scale,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

final class _Background extends StatelessWidget {
  const _Background({required this.definition});

  final StudioBackgroundDefinition definition;

  @override
  Widget build(BuildContext context) {
    if (definition.kind == StudioBackgroundKind.gradient) {
      return DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: definition.colors,
          ),
        ),
      );
    }
    return ImageFiltered(
      imageFilter: ImageFilter.blur(sigmaX: 4, sigmaY: 4),
      child: Transform.scale(
        scale: 1.04,
        child: Image.asset(
          definition.assetPath!,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const ColoredBox(color: PtwColors.ink),
        ),
      ),
    );
  }
}

final class _StudioImage extends StatelessWidget {
  const _StudioImage({required this.image});

  final StudioImageRef image;

  @override
  Widget build(BuildContext context) {
    final error = Container(
      color: PtwColors.ink,
      alignment: Alignment.center,
      child: const Icon(Icons.person_rounded, color: PtwColors.textOnAccent),
    );
    return switch (image.source) {
      StudioImageSource.asset => Image.asset(
        image.path!,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => error,
      ),
      StudioImageSource.memory => Image.memory(
        image.bytes!,
        fit: BoxFit.cover,
        gaplessPlayback: true,
        errorBuilder: (_, __, ___) => error,
      ),
    };
  }
}

final class _AutoFitMessage extends StatelessWidget {
  const _AutoFitMessage(this.text, {required this.scale});

  final String text;
  final double scale;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final direction = Directionality.of(context);
      final scaler = MediaQuery.textScalerOf(context);
      final base = TextStyle(
        color: PtwColors.textOnAccent,
        fontFamily: 'PtwRoboto',
        fontWeight: FontWeight.w900,
        height: 0.98,
        letterSpacing: -1.2 * scale,
        shadows: [
          Shadow(
            color: PtwColors.ink.withValues(alpha: 0.62),
            blurRadius: 2 * scale,
            offset: Offset(2 * scale, 3 * scale),
          ),
        ],
      );
      var selected = 46 * scale;
      for (var size = 46 * scale; size >= 24 * scale; size -= 1) {
        final painter = TextPainter(
          text: TextSpan(text: text, style: base.copyWith(fontSize: size)),
          textAlign: TextAlign.center,
          textDirection: direction,
          textScaler: scaler,
        )..layout(maxWidth: constraints.maxWidth);
        if (painter.height <= constraints.maxHeight) {
          selected = size;
          break;
        }
        selected = 24 * scale;
      }
      return Align(
        child: Text(
          text,
          textAlign: TextAlign.center,
          softWrap: true,
          overflow: TextOverflow.visible,
          style: base.copyWith(fontSize: selected),
        ),
      );
    },
  );
}

final class _StaticStickerLayer extends StatelessWidget {
  const _StaticStickerLayer({
    required this.placement,
    required this.definition,
    required this.canvasSize,
  });

  final StickerPlacement placement;
  final MemeStickerDefinition definition;
  final Size canvasSize;

  @override
  Widget build(BuildContext context) {
    final side = canvasSize.width * placement.scale;
    return Positioned(
      left: canvasSize.width * placement.centerX - side / 2,
      top: canvasSize.height * placement.centerY - side / 2,
      width: side,
      height: side,
      child: Transform.rotate(
        angle: placement.rotation,
        child: Image.asset(
          definition.assetPath,
          fit: BoxFit.contain,
          filterQuality: FilterQuality.high,
        ),
      ),
    );
  }
}

final class _EditableStickerLayer extends StatelessWidget {
  const _EditableStickerLayer({
    required this.placement,
    required this.definition,
    required this.canvasSize,
    required this.selected,
    required this.onSelect,
    required this.onMove,
    required this.onTransformStart,
    required this.onTransformUpdate,
  });

  final StickerPlacement placement;
  final MemeStickerDefinition definition;
  final Size canvasSize;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<Offset> onMove;
  final GestureDragStartCallback onTransformStart;
  final GestureDragUpdateCallback onTransformUpdate;

  @override
  Widget build(BuildContext context) {
    final side = canvasSize.width * placement.scale;
    return Positioned(
      left: canvasSize.width * placement.centerX - side / 2,
      top: canvasSize.height * placement.centerY - side / 2,
      width: side,
      height: side,
      child: Transform.rotate(
        angle: placement.rotation,
        child: Semantics(
          key: ValueKey('studio_canvas_sticker_${placement.instanceId}'),
          label: '${definition.label} sticker',
          selected: selected,
          child: MouseRegion(
            cursor: SystemMouseCursors.move,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  child: GestureDetector(
                    behavior: HitTestBehavior.translucent,
                    onTap: onSelect,
                    onPanStart: (_) => onSelect(),
                    onPanUpdate: (details) => onMove(details.delta),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 120),
                      decoration: BoxDecoration(
                        border:
                            selected
                                ? Border.all(
                                  color: PtwColors.textOnAccent,
                                  width: 2,
                                )
                                : null,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      padding: const EdgeInsets.all(2),
                      child: Image.asset(
                        definition.assetPath,
                        fit: BoxFit.contain,
                        filterQuality: FilterQuality.high,
                      ),
                    ),
                  ),
                ),
                if (selected)
                  Positioned(
                    right: 0,
                    bottom: 0,
                    child: MouseRegion(
                      cursor: SystemMouseCursors.resizeUpLeftDownRight,
                      child: GestureDetector(
                        key: const ValueKey('studio_transform_handle'),
                        behavior: HitTestBehavior.opaque,
                        onPanStart: onTransformStart,
                        onPanUpdate: onTransformUpdate,
                        child: Container(
                          width: 28,
                          height: 28,
                          decoration: BoxDecoration(
                            color: PtwColors.hotPink,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: PtwColors.textOnAccent,
                              width: 2,
                            ),
                            boxShadow: const [
                              BoxShadow(color: PtwColors.shadow, blurRadius: 6),
                            ],
                          ),
                          child: const Icon(
                            Icons.sync_rounded,
                            color: PtwColors.textOnAccent,
                            size: 16,
                          ),
                        ),
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
}
