import 'dart:ui';

import 'package:flutter/material.dart';

import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_typography.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import 'share_models.dart';

typedef ShareTemplateBodyBuilder =
    Widget Function(BuildContext context, ShareCardData data, double scale);

final class ShareTemplateRegistry {
  const ShareTemplateRegistry();

  static final Map<ShareTemplateType, ShareTemplateBodyBuilder> _builders = {
    ShareTemplateType.challenge: _challengeBody,
    ShareTemplateType.criticism: _criticismBody,
    ShareTemplateType.progress: _progressBody,
    ShareTemplateType.milestone: _milestoneBody,
    ShareTemplateType.result: _resultBody,
    ShareTemplateType.opinionChange: _opinionChangeBody,
  };

  Widget build(BuildContext context, ShareCardData data, double scale) =>
      _builders[data.template]!(context, data, scale);
}

final class ShareCard extends StatelessWidget {
  const ShareCard({
    required this.data,
    required this.format,
    super.key,
    this.registry = const ShareTemplateRegistry(),
  });

  final ShareCardData data;
  final ShareFormat format;
  final ShareTemplateRegistry registry;

  @override
  Widget build(BuildContext context) => Semantics(
    label: '${data.template.label} share card for ${data.challengeTitle}',
    image: true,
    child: AspectRatio(
      aspectRatio: format.aspectRatio,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth;
          final scale = (width / 340).clamp(0.62, 1.35);
          final inset = (width * 0.065).clamp(16.0, 38.0);
          final primary = Color(data.primaryColor);
          return ClipRect(
            child: Stack(
              fit: StackFit.expand,
              children: [
                ImageFiltered(
                  imageFilter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
                  child: Transform.scale(
                    scale: 1.12,
                    child: PtwMediaImage(image: data.background),
                  ),
                ),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: _gradient(primary, data.gradientVariant, format),
                  ),
                ),
                Padding(
                  padding: EdgeInsets.fromLTRB(
                    inset,
                    inset,
                    inset,
                    inset * 0.82,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _CardHeader(data: data, scale: scale),
                      SizedBox(height: 16 * scale),
                      Expanded(child: registry.build(context, data, scale)),
                      SizedBox(height: 12 * scale),
                      _CardFooter(data: data, scale: scale),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    ),
  );

  LinearGradient _gradient(Color primary, int variant, ShareFormat format) {
    final dark = Color.lerp(primary, PtwColors.ink, 0.64)!;
    final hot = Color.lerp(primary, PtwColors.hotPink, 0.35)!;
    return switch (variant % 3) {
      1 => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        stops: const [0, 0.48, 1],
        colors: [
          dark.withValues(alpha: 0.72),
          hot.withValues(alpha: 0.72),
          PtwColors.ink.withValues(alpha: 0.92),
        ],
      ),
      2 => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        stops: const [0, 0.44, 1],
        colors: [
          primary.withValues(alpha: 0.46),
          PtwColors.ink.withValues(alpha: 0.54),
          dark.withValues(alpha: 0.96),
        ],
      ),
      _ => LinearGradient(
        begin:
            format == ShareFormat.square
                ? Alignment.topLeft
                : Alignment.topCenter,
        end: Alignment.bottomRight,
        stops: const [0, 0.52, 1],
        colors: [
          PtwColors.ink.withValues(alpha: 0.46),
          primary.withValues(alpha: 0.76),
          PtwColors.ink.withValues(alpha: 0.94),
        ],
      ),
    };
  }
}

final class _CardHeader extends StatelessWidget {
  const _CardHeader({required this.data, required this.scale});

  final ShareCardData data;
  final double scale;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        width: 34 * scale,
        height: 34 * scale,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: PtwColors.textOnAccent, width: 1.5),
        ),
        child: Image.asset(data.ownerAvatarAsset, fit: BoxFit.cover),
      ),
      SizedBox(width: 9 * scale),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              data.ownerName,
              maxLines: 1,
              style: PtwTypography.bodyStrong.copyWith(
                color: PtwColors.textOnAccent,
                fontSize: 13 * scale,
                height: 1,
              ),
            ),
            SizedBox(height: 3 * scale),
            Text(
              '@${data.ownerHandle}',
              maxLines: 1,
              style: PtwTypography.caption.copyWith(
                color: PtwColors.textOnAccent.withValues(alpha: 0.74),
                fontSize: 9.5 * scale,
                height: 1,
              ),
            ),
          ],
        ),
      ),
      Container(
        padding: EdgeInsets.symmetric(
          horizontal: 9 * scale,
          vertical: 5 * scale,
        ),
        decoration: BoxDecoration(
          color: PtwColors.ink.withValues(alpha: 0.56),
          border: Border.all(
            color: PtwColors.textOnAccent.withValues(alpha: 0.7),
          ),
          borderRadius: BorderRadius.circular(PtwRadius.pill),
        ),
        child: Text(
          data.template.label.toUpperCase(),
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontSize: 8.5 * scale,
            height: 1,
            fontWeight: FontWeight.w900,
            letterSpacing: 0.8,
          ),
        ),
      ),
    ],
  );
}

final class _CardFooter extends StatelessWidget {
  const _CardFooter({required this.data, required this.scale});

  final ShareCardData data;
  final double scale;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Text(
          data.cta,
          style: PtwTypography.bodyStrong.copyWith(
            color: PtwColors.textOnAccent,
            fontSize: 11.5 * scale,
            height: 1.15,
          ),
        ),
      ),
      SizedBox(width: 8 * scale),
      Text(
        'PTW',
        style: TextStyle(
          color: PtwColors.textOnAccent,
          fontFamily: 'PtwLilitaOne',
          fontSize: 18 * scale,
          height: 1,
          letterSpacing: 0.4,
          shadows: const [Shadow(color: PtwColors.ink, offset: Offset(2, 2))],
        ),
      ),
    ],
  );
}

Widget _challengeBody(BuildContext context, ShareCardData data, double scale) =>
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(flex: 2),
        _Overline('I WILL', scale: scale),
        SizedBox(height: 8 * scale),
        Expanded(
          flex: 7,
          child: _AutoText(
            data.challengeTitle,
            maxFontSize: 43 * scale,
            minFontSize: 20 * scale,
            style: _heroStyle(scale),
          ),
        ),
        SizedBox(height: 8 * scale),
        Text(
          PtwFormatters.deadline(data.deadline),
          style: PtwTypography.bodyStrong.copyWith(
            color: PtwColors.textOnAccent.withValues(alpha: 0.82),
            fontSize: 12 * scale,
          ),
        ),
        const Spacer(),
        Flexible(
          flex: 3,
          child: _AutoText(
            data.hook,
            maxFontSize: 26 * scale,
            minFontSize: 15 * scale,
            style: _hookStyle(scale),
          ),
        ),
      ],
    );

Widget _criticismBody(BuildContext context, ShareCardData data, double scale) =>
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        _Overline('THEY SAID', scale: scale),
        SizedBox(height: 10 * scale),
        Expanded(
          flex: 6,
          child: Container(
            width: double.infinity,
            padding: EdgeInsets.all(18 * scale),
            decoration: BoxDecoration(
              color: PtwColors.softWhite,
              borderRadius: BorderRadius.circular(22 * scale),
              border: Border.all(color: PtwColors.textOnAccent),
            ),
            child: _AutoText(
              '“${data.featuredComment}”',
              maxFontSize: 28 * scale,
              minFontSize: 15 * scale,
              style: PtwTypography.titleLarge.copyWith(
                color: PtwColors.ink,
                height: 1.02,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ),
        SizedBox(height: 16 * scale),
        _Overline('MY RESPONSE', scale: scale),
        SizedBox(height: 5 * scale),
        Flexible(
          flex: 3,
          child: _AutoText(
            data.hook,
            maxFontSize: 29 * scale,
            minFontSize: 16 * scale,
            style: _hookStyle(scale),
          ),
        ),
        const Spacer(),
      ],
    );

Widget _progressBody(BuildContext context, ShareCardData data, double scale) =>
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        _Overline('DAY ${data.dayNumber}', scale: scale),
        SizedBox(height: 5 * scale),
        Flexible(
          flex: 4,
          child: _AutoText(
            data.progressValue,
            maxFontSize: 76 * scale,
            minFontSize: 34 * scale,
            style: _heroStyle(scale).copyWith(height: 0.88),
          ),
        ),
        Text(
          data.progressMetric.toUpperCase(),
          style: PtwTypography.bodyStrong.copyWith(
            color: PtwColors.textOnAccent,
            fontSize: 12 * scale,
            letterSpacing: 1,
          ),
        ),
        SizedBox(height: 5 * scale),
        Text(
          data.progressSecondary,
          style: PtwTypography.body.copyWith(
            color: PtwColors.textOnAccent.withValues(alpha: 0.78),
            fontSize: 11 * scale,
          ),
        ),
        const Spacer(flex: 2),
        Flexible(
          flex: 3,
          child: _AutoText(
            data.hook,
            maxFontSize: 27 * scale,
            minFontSize: 15 * scale,
            style: _hookStyle(scale),
          ),
        ),
        const Spacer(),
      ],
    );

Widget _milestoneBody(BuildContext context, ShareCardData data, double scale) =>
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        Container(
          width: 52 * scale,
          height: 52 * scale,
          decoration: BoxDecoration(
            color: PtwColors.textOnAccent,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: PtwColors.ink.withValues(alpha: 0.34),
                offset: Offset(4 * scale, 5 * scale),
              ),
            ],
          ),
          child: Icon(
            Icons.flag_rounded,
            size: 27 * scale,
            color: Color(data.primaryColor),
          ),
        ),
        SizedBox(height: 18 * scale),
        _Overline('MILESTONE', scale: scale),
        SizedBox(height: 7 * scale),
        Expanded(
          flex: 5,
          child: _AutoText(
            data.milestone,
            maxFontSize: 39 * scale,
            minFontSize: 19 * scale,
            style: _heroStyle(scale),
          ),
        ),
        Text(
          data.progressSecondary,
          maxLines: 3,
          style: PtwTypography.body.copyWith(
            color: PtwColors.textOnAccent.withValues(alpha: 0.78),
            fontSize: 11 * scale,
          ),
        ),
        SizedBox(height: 14 * scale),
        Flexible(
          flex: 2,
          child: _AutoText(
            data.hook,
            maxFontSize: 22 * scale,
            minFontSize: 14 * scale,
            style: _hookStyle(scale),
          ),
        ),
        const Spacer(),
      ],
    );

Widget _resultBody(BuildContext context, ShareCardData data, double scale) =>
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        _Overline(data.resultLead.toUpperCase(), scale: scale),
        SizedBox(height: 6 * scale),
        Flexible(
          flex: 3,
          child: _AutoText(
            '${data.doubtPercent}% believed I would fail.',
            maxFontSize: 29 * scale,
            minFontSize: 15 * scale,
            style: _hookStyle(scale),
          ),
        ),
        SizedBox(height: 17 * scale),
        Container(
          width: 44 * scale,
          height: 3 * scale,
          color: PtwColors.textOnAccent,
        ),
        SizedBox(height: 17 * scale),
        _Overline('TODAY', scale: scale),
        SizedBox(height: 6 * scale),
        Expanded(
          flex: 5,
          child: _AutoText(
            data.resultOutcome,
            maxFontSize: 48 * scale,
            minFontSize: 23 * scale,
            style: _heroStyle(scale),
          ),
        ),
        Flexible(
          flex: 2,
          child: _AutoText(
            data.hook,
            maxFontSize: 22 * scale,
            minFontSize: 14 * scale,
            style: _hookStyle(scale),
          ),
        ),
        const Spacer(),
      ],
    );

Widget _opinionChangeBody(
  BuildContext context,
  ShareCardData data,
  double scale,
) => Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  children: [
    const Spacer(),
    _Overline('THEN', scale: scale),
    SizedBox(height: 7 * scale),
    Flexible(
      flex: 3,
      child: Container(
        width: double.infinity,
        padding: EdgeInsets.all(14 * scale),
        decoration: BoxDecoration(
          color: PtwColors.ink.withValues(alpha: 0.62),
          border: Border.all(
            color: PtwColors.textOnAccent.withValues(alpha: 0.78),
          ),
          borderRadius: BorderRadius.circular(18 * scale),
        ),
        child: _AutoText(
          '“${data.featuredComment}”',
          maxFontSize: 22 * scale,
          minFontSize: 13 * scale,
          style: _hookStyle(scale),
        ),
      ),
    ),
    Padding(
      padding: EdgeInsets.symmetric(vertical: 8 * scale),
      child: Icon(
        Icons.south_rounded,
        color: PtwColors.textOnAccent,
        size: 27 * scale,
      ),
    ),
    _Overline('NOW', scale: scale),
    SizedBox(height: 6 * scale),
    Expanded(
      flex: 4,
      child: _AutoText(
        data.opinionChange,
        maxFontSize: 36 * scale,
        minFontSize: 18 * scale,
        style: _heroStyle(scale),
      ),
    ),
    Flexible(
      flex: 2,
      child: _AutoText(
        data.hook,
        maxFontSize: 20 * scale,
        minFontSize: 13 * scale,
        style: _hookStyle(scale),
      ),
    ),
    const Spacer(),
  ],
);

TextStyle _heroStyle(double scale) => TextStyle(
  fontFamily: 'PtwLilitaOne',
  color: PtwColors.textOnAccent,
  height: 0.96,
  shadows: [Shadow(color: PtwColors.ink, offset: Offset(3 * scale, 3 * scale))],
);

TextStyle _hookStyle(double scale) => PtwTypography.titleLarge.copyWith(
  color: PtwColors.textOnAccent,
  height: 1.02,
  fontWeight: FontWeight.w900,
  shadows: [
    Shadow(
      color: PtwColors.ink.withValues(alpha: 0.64),
      offset: Offset(2 * scale, 2 * scale),
    ),
  ],
);

final class _Overline extends StatelessWidget {
  const _Overline(this.text, {required this.scale});

  final String text;
  final double scale;

  @override
  Widget build(BuildContext context) => Text(
    text,
    maxLines: 2,
    style: PtwTypography.caption.copyWith(
      color: PtwColors.textOnAccent.withValues(alpha: 0.82),
      fontSize: 9.5 * scale,
      height: 1.1,
      fontWeight: FontWeight.w900,
      letterSpacing: 1.3,
    ),
  );
}

final class _AutoText extends StatelessWidget {
  const _AutoText(
    this.text, {
    required this.maxFontSize,
    required this.minFontSize,
    required this.style,
  });

  final String text;
  final double maxFontSize;
  final double minFontSize;
  final TextStyle style;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final textDirection = Directionality.of(context);
      final textScaler = MediaQuery.textScalerOf(context);
      var selected = maxFontSize;
      for (var size = maxFontSize; size >= minFontSize; size -= 1) {
        final painter = TextPainter(
          text: TextSpan(text: text, style: style.copyWith(fontSize: size)),
          textDirection: textDirection,
          textScaler: textScaler,
        )..layout(maxWidth: constraints.maxWidth);
        if (painter.height <= constraints.maxHeight) {
          selected = size;
          break;
        }
        selected = minFontSize;
      }
      return Align(
        alignment: Alignment.centerLeft,
        child: Text(
          text,
          softWrap: true,
          overflow: TextOverflow.visible,
          style: style.copyWith(fontSize: selected),
        ),
      );
    },
  );
}
