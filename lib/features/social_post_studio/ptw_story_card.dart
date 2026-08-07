import 'dart:ui';

import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import '../../models/ptw_story_composition.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import 'ptw_story_constructor_controller.dart';
import 'studio_models.dart';

enum PtwStoryTextTarget { headline, dare }

final class PtwStoryCard extends StatelessWidget {
  const PtwStoryCard({
    required this.composition,
    required this.catalog,
    super.key,
  });

  static const logicalSize = Size(360, 640);
  static const exportSize = Size(1080, 1920);

  final PtwStoryComposition composition;
  final MemeStickerCatalog catalog;

  @override
  Widget build(BuildContext context) =>
      _StoryCanvas(composition: composition, catalog: catalog);
}

final class EditablePtwStoryCard extends StatelessWidget {
  const EditablePtwStoryCard({
    required this.controller,
    this.selectedText,
    this.onTextSelected,
    this.onCanvasTap,
    this.onStickerSelected,
    super.key,
  });

  final PtwStoryConstructorController controller;
  final PtwStoryTextTarget? selectedText;
  final ValueChanged<PtwStoryTextTarget>? onTextSelected;
  final VoidCallback? onCanvasTap;
  final VoidCallback? onStickerSelected;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder:
        (_, __) => _StoryCanvas(
          composition: controller.composition,
          catalog: controller.catalog,
          controller: controller,
          selectedText: selectedText,
          onTextSelected: onTextSelected,
          onCanvasTap: onCanvasTap,
          onStickerSelected: onStickerSelected,
        ),
  );
}

final class _StoryCanvas extends StatelessWidget {
  const _StoryCanvas({
    required this.composition,
    required this.catalog,
    this.controller,
    this.selectedText,
    this.onTextSelected,
    this.onCanvasTap,
    this.onStickerSelected,
  });

  final PtwStoryComposition composition;
  final MemeStickerCatalog catalog;
  final PtwStoryConstructorController? controller;
  final PtwStoryTextTarget? selectedText;
  final ValueChanged<PtwStoryTextTarget>? onTextSelected;
  final VoidCallback? onCanvasTap;
  final VoidCallback? onStickerSelected;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final size = constraints.biggest;
      final scale = size.width / PtwStoryCard.logicalSize.width;
      return ClipRect(
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () {
            controller?.selectSticker(null);
            onCanvasTap?.call();
          },
          child: Stack(
            fit: StackFit.expand,
            children: [
              _StoryBackground(composition: composition),
              _StoryOverlay(treatment: composition.textTreatment),
              Positioned(
                left: 0,
                right: 0,
                top: 72 * scale,
                child: Center(
                  child: Container(
                    width: 76 * scale,
                    height: 76 * scale,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: PtwColors.textOnAccent,
                        width: 4 * scale,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: PtwColors.ink.withValues(alpha: 0.34),
                          blurRadius: 12 * scale,
                          offset: Offset(0, 5 * scale),
                        ),
                      ],
                    ),
                    child: PtwMediaImage(image: composition.avatar),
                  ),
                ),
              ),
              Positioned(
                left: 30 * scale,
                right: 30 * scale,
                top: 181 * scale,
                height: 250 * scale,
                child: _EditableTextRegion(
                  key: const ValueKey('story_canvas_headline'),
                  selected: selectedText == PtwStoryTextTarget.headline,
                  onTap:
                      onTextSelected == null
                          ? null
                          : () => onTextSelected!(PtwStoryTextTarget.headline),
                  borderRadius: 20 * scale,
                  child: _StoryHeadline(
                    text: composition.headline,
                    treatment: composition.textTreatment,
                    scale: scale,
                  ),
                ),
              ),
              Positioned(
                left: 30 * scale,
                right: 30 * scale,
                top: 448 * scale,
                height: 68 * scale,
                child: _EditableTextRegion(
                  key: const ValueKey('story_canvas_dare'),
                  selected: selectedText == PtwStoryTextTarget.dare,
                  onTap:
                      onTextSelected == null
                          ? null
                          : () => onTextSelected!(PtwStoryTextTarget.dare),
                  borderRadius: 16 * scale,
                  child: Center(
                    child: Text(
                      composition.dare,
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: _dareStyle(composition.textTreatment, scale),
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 23 * scale,
                bottom: 22 * scale,
                child: Text(
                  'PTW',
                  style: TextStyle(
                    color: _brandColor(composition.textTreatment),
                    fontFamily: 'PtwLilitaOne',
                    fontSize: 25 * scale,
                    height: 1,
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
                right: 23 * scale,
                bottom: 24 * scale,
                child: Text(
                  'PROVE THEM WRONG',
                  style: TextStyle(
                    color: _foreground(
                      composition.textTreatment,
                    ).withValues(alpha: 0.86),
                    fontFamily: 'PtwRoboto',
                    fontSize: 8.5 * scale,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.1 * scale,
                  ),
                ),
              ),
              for (final placement in composition.stickers)
                _StorySticker(
                  placement: placement,
                  assetPath: catalog.byId(placement.stickerId).assetPath,
                  canvasSize: size,
                  controller: controller,
                  onSelected: onStickerSelected,
                  selected:
                      controller?.selectedStickerId == placement.instanceId,
                ),
            ],
          ),
        ),
      );
    },
  );
}

final class _EditableTextRegion extends StatelessWidget {
  const _EditableTextRegion({
    required this.selected,
    required this.onTap,
    required this.borderRadius,
    required this.child,
    super.key,
  });

  final bool selected;
  final VoidCallback? onTap;
  final double borderRadius;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (onTap == null && !selected) return child;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        decoration: BoxDecoration(
          color:
              selected
                  ? PtwColors.ink.withValues(alpha: 0.12)
                  : PtwColors.transparent,
          borderRadius: BorderRadius.circular(borderRadius),
          border:
              selected
                  ? Border.all(color: PtwColors.accentYellow, width: 2)
                  : null,
        ),
        child: child,
      ),
    );
  }
}

final class _StoryBackground extends StatelessWidget {
  const _StoryBackground({required this.composition});

  final PtwStoryComposition composition;

  @override
  Widget build(BuildContext context) {
    final id = composition.backgroundId;
    if (id == null) {
      return ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: 3, sigmaY: 3),
        child: Transform.scale(
          scale: 1.035,
          child: PtwMediaImage(image: composition.projectBackground),
        ),
      );
    }
    final background = StudioBackgrounds.byId(id);
    if (background.kind == StudioBackgroundKind.gradient) {
      return DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: background.colors,
          ),
        ),
      );
    }
    return ImageFiltered(
      imageFilter: ImageFilter.blur(sigmaX: 3, sigmaY: 3),
      child: Transform.scale(
        scale: 1.035,
        child: Image.asset(background.assetPath!, fit: BoxFit.cover),
      ),
    );
  }
}

final class _StoryOverlay extends StatelessWidget {
  const _StoryOverlay({required this.treatment});

  final PtwStoryTextTreatment treatment;

  @override
  Widget build(BuildContext context) {
    final dark = treatment != PtwStoryTextTreatment.chaos;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors:
              dark
                  ? [
                    PtwColors.ink.withValues(alpha: 0.12),
                    PtwColors.ink.withValues(alpha: 0.26),
                    PtwColors.ink.withValues(alpha: 0.68),
                  ]
                  : [
                    PtwColors.transparent,
                    PtwColors.textOnAccent.withValues(alpha: 0.04),
                    PtwColors.ink.withValues(alpha: 0.12),
                  ],
        ),
      ),
    );
  }
}

final class _StoryHeadline extends StatelessWidget {
  const _StoryHeadline({
    required this.text,
    required this.treatment,
    required this.scale,
  });

  final String text;
  final PtwStoryTextTreatment treatment;
  final double scale;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final base = _headlineStyle(treatment, scale);
      var size = 43 * scale;
      for (var candidate = 43 * scale; candidate >= 23 * scale; candidate--) {
        final painter = TextPainter(
          text: TextSpan(text: text, style: base.copyWith(fontSize: candidate)),
          textAlign: TextAlign.center,
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
          maxLines: 5,
        )..layout(maxWidth: constraints.maxWidth);
        size = candidate;
        if (!painter.didExceedMaxLines &&
            painter.height <= constraints.maxHeight) {
          break;
        }
      }
      return Center(
        child: Text(
          text,
          textAlign: TextAlign.center,
          maxLines: 5,
          overflow: TextOverflow.ellipsis,
          style: base.copyWith(fontSize: size),
        ),
      );
    },
  );
}

final class _StorySticker extends StatefulWidget {
  const _StorySticker({
    required this.placement,
    required this.assetPath,
    required this.canvasSize,
    required this.selected,
    this.onSelected,
    this.controller,
  });

  final PtwStoryStickerPlacement placement;
  final String assetPath;
  final Size canvasSize;
  final bool selected;
  final VoidCallback? onSelected;
  final PtwStoryConstructorController? controller;

  @override
  State<_StorySticker> createState() => _StoryStickerState();
}

final class _StoryStickerState extends State<_StorySticker> {
  late PtwStoryStickerPlacement _start;
  final _layerKey = GlobalKey();
  Offset? _transformCenterGlobal;
  double _transformStartDistance = 1;
  double _transformStartAngle = 0;
  double _transformStartScale = 0;
  double _transformStartRotation = 0;

  @override
  Widget build(BuildContext context) {
    final side = widget.canvasSize.width * widget.placement.scale;
    return Positioned(
      left: widget.canvasSize.width * widget.placement.centerX - side / 2,
      top: widget.canvasSize.height * widget.placement.centerY - side / 2,
      width: side,
      height: side,
      child: Transform.rotate(
        angle: widget.placement.rotation,
        child: Stack(
          key: _layerKey,
          clipBehavior: Clip.none,
          children: [
            Positioned.fill(
              child: GestureDetector(
                key: ValueKey(
                  'story_canvas_sticker_${widget.placement.instanceId}',
                ),
                behavior: HitTestBehavior.opaque,
                onTap: _select,
                onScaleStart: (_) {
                  _start = widget.placement;
                  _select();
                },
                onScaleUpdate: (details) {
                  final controller = widget.controller;
                  if (controller == null) return;
                  controller.updateSticker(
                    widget.placement.instanceId,
                    centerX:
                        widget.placement.centerX +
                        details.focalPointDelta.dx / widget.canvasSize.width,
                    centerY:
                        widget.placement.centerY +
                        details.focalPointDelta.dy / widget.canvasSize.height,
                    scale: _start.scale * details.scale,
                    rotation: _start.rotation + details.rotation,
                  );
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 100),
                  padding: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    border:
                        widget.selected
                            ? Border.all(
                              color: PtwColors.textOnAccent,
                              width: 2,
                            )
                            : null,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Image.asset(widget.assetPath, fit: BoxFit.contain),
                ),
              ),
            ),
            if (widget.selected && widget.controller != null) ...[
              Positioned(
                left: 0,
                top: 0,
                child: _StickerHandle(
                  key: const ValueKey('story_delete_sticker'),
                  icon: Icons.close_rounded,
                  onTap: () {
                    _select();
                    widget.controller!.removeSelected();
                  },
                ),
              ),
              Positioned(
                right: 0,
                bottom: 0,
                child: _StickerHandle(
                  key: const ValueKey('story_transform_handle'),
                  icon: Icons.sync_rounded,
                  onPanStart: _startHandleTransform,
                  onPanUpdate: _updateHandleTransform,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _select() {
    widget.controller?.selectSticker(widget.placement.instanceId);
    widget.onSelected?.call();
  }

  void _startHandleTransform(DragStartDetails details) {
    final box = _layerKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return;
    final center = box.localToGlobal(box.size.center(Offset.zero));
    final vector = details.globalPosition - center;
    _transformCenterGlobal = center;
    _transformStartDistance = vector.distance.clamp(1, double.infinity);
    _transformStartAngle = vector.direction;
    _transformStartScale = widget.placement.scale;
    _transformStartRotation = widget.placement.rotation;
    _select();
  }

  void _updateHandleTransform(DragUpdateDetails details) {
    final center = _transformCenterGlobal;
    final controller = widget.controller;
    if (center == null || controller == null) return;
    final vector = details.globalPosition - center;
    controller.updateSticker(
      widget.placement.instanceId,
      scale: _transformStartScale * (vector.distance / _transformStartDistance),
      rotation:
          _transformStartRotation + vector.direction - _transformStartAngle,
    );
  }
}

final class _StickerHandle extends StatelessWidget {
  const _StickerHandle({
    required this.icon,
    this.onTap,
    this.onPanStart,
    this.onPanUpdate,
    super.key,
  });

  final IconData icon;
  final VoidCallback? onTap;
  final GestureDragStartCallback? onPanStart;
  final GestureDragUpdateCallback? onPanUpdate;

  @override
  Widget build(BuildContext context) => GestureDetector(
    behavior: HitTestBehavior.opaque,
    onTap: onTap,
    onPanStart: onPanStart,
    onPanUpdate: onPanUpdate,
    child: Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        color: PtwColors.hotPink,
        shape: BoxShape.circle,
        border: Border.all(color: PtwColors.textOnAccent, width: 2),
        boxShadow: const [BoxShadow(color: PtwColors.shadow, blurRadius: 6)],
      ),
      child: Icon(icon, color: PtwColors.textOnAccent, size: 17),
    ),
  );
}

TextStyle _headlineStyle(PtwStoryTextTreatment treatment, double scale) =>
    TextStyle(
      color: _foreground(treatment),
      fontFamily:
          treatment == PtwStoryTextTreatment.clean
              ? 'PtwRoboto'
              : 'PtwLilitaOne',
      fontWeight: FontWeight.w900,
      height: 0.96,
      letterSpacing: -0.7 * scale,
      fontStyle:
          treatment == PtwStoryTextTreatment.candy
              ? FontStyle.italic
              : FontStyle.normal,
      shadows: [
        if (treatment == PtwStoryTextTreatment.candy)
          Shadow(color: const Color(0xFFFFE800), offset: Offset(0, 4 * scale))
        else
          Shadow(
            color: PtwColors.ink.withValues(alpha: 0.88),
            offset: Offset(2.5 * scale, 3 * scale),
          ),
      ],
    );

TextStyle _dareStyle(PtwStoryTextTreatment treatment, double scale) =>
    TextStyle(
      color: _foreground(treatment),
      fontFamily: 'PtwRoboto',
      fontSize: 21 * scale,
      height: 1.05,
      fontWeight: FontWeight.w900,
      shadows: [
        Shadow(
          color: PtwColors.ink.withValues(alpha: 0.85),
          offset: Offset(1.5 * scale, 2 * scale),
        ),
      ],
    );

Color _foreground(PtwStoryTextTreatment treatment) => switch (treatment) {
  PtwStoryTextTreatment.candy => PtwColors.hotPink,
  PtwStoryTextTreatment.chaos => PtwColors.ink,
  _ => PtwColors.textOnAccent,
};

Color _brandColor(PtwStoryTextTreatment treatment) =>
    treatment == PtwStoryTextTreatment.chaos
        ? PtwColors.hotPink
        : PtwColors.textOnAccent;
