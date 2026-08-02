import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';

enum PtwStickerVariant { hero, project, action, actionSheet }

enum PtwStickerSurface { saturated, dark }

/// High-impact display text reserved for identity, state, and primary actions.
///
/// The outline is built from zero-blur shadows so this remains one real [Text]
/// widget for accessibility, wrapping, and stable widget tests.
final class PtwStickerText extends StatelessWidget {
  const PtwStickerText.hero(
    this.text, {
    super.key,
    this.textAlign = TextAlign.start,
    this.maxLines,
  }) : variant = PtwStickerVariant.hero,
       surface = PtwStickerSurface.saturated,
       accentColor = PtwColors.hotPink,
       compact = false,
       enabled = true,
       alignment = null;

  const PtwStickerText.project(
    this.text, {
    super.key,
    this.compact = false,
    this.textAlign = TextAlign.start,
    this.maxLines,
    this.alignment = Alignment.bottomLeft,
  }) : variant = PtwStickerVariant.project,
       surface = PtwStickerSurface.saturated,
       accentColor = PtwColors.hotPink,
       enabled = true;

  const PtwStickerText.action(
    this.text, {
    super.key,
    this.accentColor = PtwColors.hotPink,
    this.enabled = true,
    this.textAlign = TextAlign.center,
    this.maxLines = 1,
  }) : variant = PtwStickerVariant.action,
       surface = PtwStickerSurface.dark,
       compact = false,
       alignment = null;

  const PtwStickerText.actionSheet(
    this.text, {
    super.key,
    this.accentColor = PtwColors.hotPink,
    this.enabled = true,
    this.textAlign = TextAlign.start,
    this.maxLines,
  }) : variant = PtwStickerVariant.actionSheet,
       surface = PtwStickerSurface.dark,
       compact = false,
       alignment = null;

  static const fontFamily = 'PtwLilitaOne';

  final String text;
  final PtwStickerVariant variant;
  final PtwStickerSurface surface;
  final Color accentColor;
  final bool compact;
  final bool enabled;
  final TextAlign textAlign;
  final int? maxLines;
  final Alignment? alignment;

  double get _maximumFontSize => switch (variant) {
    PtwStickerVariant.hero => 44,
    PtwStickerVariant.project => compact ? 30 : 38,
    PtwStickerVariant.action => 18,
    PtwStickerVariant.actionSheet => 28,
  };

  double get _minimumFontSize => switch (variant) {
    PtwStickerVariant.project => compact ? 20 : 22,
    _ => _maximumFontSize,
  };

  Color _withEnabledOpacity(Color color) =>
      enabled ? color : color.withValues(alpha: 0.55);

  TextStyle _style(double fontSize) {
    final fill = _withEnabledOpacity(
      surface == PtwStickerSurface.dark ? accentColor : PtwColors.textOnAccent,
    );
    final outline = _withEnabledOpacity(
      surface == PtwStickerSurface.dark
          ? PtwColors.textOnAccent
          : PtwColors.ink,
    );
    final shadows = <Shadow>[
      ..._outlineShadows(
        color: outline,
        radius: surface == PtwStickerSurface.dark ? 1 : 2,
      ),
      if (surface == PtwStickerSurface.saturated)
        Shadow(
          color: _withEnabledOpacity(PtwColors.ink),
          offset: const Offset(3, 3),
        ),
    ];
    return TextStyle(
      fontFamily: fontFamily,
      fontSize: fontSize,
      height: 0.96,
      color: fill,
      shadows: shadows,
    );
  }

  List<Shadow> _outlineShadows({required Color color, required double radius}) {
    if (radius == 1) {
      return <Shadow>[
        for (final offset in const <Offset>[
          Offset(-1, -1),
          Offset(0, -1),
          Offset(1, -1),
          Offset(-1, 0),
          Offset(1, 0),
          Offset(-1, 1),
          Offset(0, 1),
          Offset(1, 1),
        ])
          Shadow(color: color, offset: offset),
      ];
    }
    return <Shadow>[
      for (final offset in const <Offset>[
        Offset(-2, -2),
        Offset(-1, -2),
        Offset(0, -2),
        Offset(1, -2),
        Offset(2, -2),
        Offset(-2, -1),
        Offset(2, -1),
        Offset(-2, 0),
        Offset(2, 0),
        Offset(-2, 1),
        Offset(2, 1),
        Offset(-2, 2),
        Offset(-1, 2),
        Offset(0, 2),
        Offset(1, 2),
        Offset(2, 2),
      ])
        Shadow(color: color, offset: offset),
    ];
  }

  Text _text(double fontSize) => Text(
    text,
    textAlign: textAlign,
    maxLines: maxLines,
    softWrap: true,
    overflow: TextOverflow.visible,
    style: _style(fontSize),
  );

  double _fittedFontSize(BuildContext context, BoxConstraints constraints) {
    final textScaler = MediaQuery.textScalerOf(context);
    final textDirection = Directionality.of(context);
    final maxWidth =
        constraints.hasBoundedWidth ? constraints.maxWidth : double.infinity;
    final maxHeight =
        constraints.hasBoundedHeight ? constraints.maxHeight : double.infinity;
    for (
      var fontSize = _maximumFontSize;
      fontSize >= _minimumFontSize;
      fontSize -= 1
    ) {
      final painter = TextPainter(
        text: TextSpan(text: text, style: _style(fontSize)),
        textAlign: textAlign,
        textDirection: textDirection,
        textScaler: textScaler,
        maxLines: maxLines,
      )..layout(maxWidth: maxWidth);
      if (!painter.didExceedMaxLines && painter.height <= maxHeight) {
        return fontSize;
      }
    }
    return _minimumFontSize;
  }

  @override
  Widget build(BuildContext context) {
    if (variant != PtwStickerVariant.project) {
      return _text(_maximumFontSize);
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final child = _text(_fittedFontSize(context, constraints));
        return alignment == null
            ? child
            : Align(alignment: alignment!, child: child);
      },
    );
  }
}
