import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import 'share_models.dart';
import 'share_platform_style.dart';

Future<void> showPtwShareGuide({
  required BuildContext context,
  required ShareAsset asset,
  required ShareCardData card,
  required SharePlatformGuide guide,
}) => showGeneralDialog<void>(
  context: context,
  barrierDismissible: false,
  barrierLabel: 'Share guide',
  barrierColor: PtwColors.ink.withValues(alpha: 0.72),
  transitionDuration: const Duration(milliseconds: 240),
  pageBuilder:
      (context, animation, secondaryAnimation) =>
          _ShareGuideDialog(asset: asset, card: card, guide: guide),
  transitionBuilder:
      (context, animation, secondaryAnimation, child) => FadeTransition(
        opacity: CurvedAnimation(parent: animation, curve: Curves.easeOut),
        child: ScaleTransition(
          scale: Tween(begin: 0.97, end: 1.0).animate(animation),
          child: child,
        ),
      ),
);

final class _ShareGuideDialog extends StatefulWidget {
  const _ShareGuideDialog({
    required this.asset,
    required this.card,
    required this.guide,
  });

  final ShareAsset asset;
  final ShareCardData card;
  final SharePlatformGuide guide;

  @override
  State<_ShareGuideDialog> createState() => _ShareGuideDialogState();
}

final class _ShareGuideDialogState extends State<_ShareGuideDialog> {
  int _step = 0;
  bool _showComposer = false;

  void _next() {
    if (_step == widget.guide.steps.length - 1) {
      setState(() => _showComposer = true);
      return;
    }
    setState(() => _step++);
  }

  @override
  Widget build(BuildContext context) => Material(
    color: PtwColors.transparent,
    child: BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
      child: SafeArea(child: _showComposer ? _composer() : _guide()),
    ),
  );

  Widget _guide() {
    final step = widget.guide.steps[_step];
    return Padding(
      key: const ValueKey(ComponentIds.storyShareGuide),
      padding: const EdgeInsets.fromLTRB(
        PtwSpacing.md,
        PtwSpacing.xs,
        PtwSpacing.md,
        PtwSpacing.md,
      ),
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: IconButton(
              tooltip: 'Close',
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(
                Icons.close_rounded,
                color: PtwColors.textOnAccent,
                size: 34,
              ),
            ),
          ),
          Expanded(
            child: LayoutBuilder(
              builder:
                  (context, constraints) => SingleChildScrollView(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        minHeight: constraints.maxHeight,
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          _PlatformRail(selected: widget.guide.platform),
                          const SizedBox(height: PtwSpacing.md),
                          Container(
                            constraints: const BoxConstraints(maxWidth: 500),
                            padding: const EdgeInsets.all(PtwSpacing.lg),
                            decoration: BoxDecoration(
                              color: PtwColors.surfacePrimary,
                              borderRadius: BorderRadius.circular(PtwRadius.xl),
                              boxShadow: const [
                                BoxShadow(
                                  color: PtwColors.shadow,
                                  blurRadius: 28,
                                  offset: Offset(0, 14),
                                ),
                              ],
                            ),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  step.title,
                                  textAlign: TextAlign.center,
                                  style: PtwTypography.titleLarge,
                                ),
                                const SizedBox(height: PtwSpacing.md),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    for (
                                      var index = 0;
                                      index < widget.guide.steps.length;
                                      index++
                                    )
                                      Container(
                                        width: 30,
                                        height: 30,
                                        margin: const EdgeInsets.symmetric(
                                          horizontal: 5,
                                        ),
                                        alignment: Alignment.center,
                                        decoration: BoxDecoration(
                                          color:
                                              index == _step
                                                  ? PtwColors.ink
                                                  : PtwColors.surfaceMuted,
                                          shape: BoxShape.circle,
                                        ),
                                        child: Text(
                                          '${index + 1}',
                                          style: PtwTypography.label.copyWith(
                                            color:
                                                index == _step
                                                    ? PtwColors.textOnAccent
                                                    : PtwColors.ink,
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: PtwSpacing.lg),
                                _GuideIllustration(
                                  kind: step.illustration,
                                  platform: widget.guide.platform,
                                  link: widget.card.publicLink,
                                ),
                                const SizedBox(height: PtwSpacing.md),
                                Text(
                                  step.body,
                                  textAlign: TextAlign.center,
                                  style: PtwTypography.body,
                                ),
                                const SizedBox(height: PtwSpacing.lg),
                                PtwBlackButton(
                                  key: ValueKey(
                                    _step == widget.guide.steps.length - 1
                                        ? ComponentIds.storyShareGuideFinish
                                        : ComponentIds.storyShareGuideNext,
                                  ),
                                  label:
                                      _step == widget.guide.steps.length - 1
                                          ? 'Share!'
                                          : 'Next step',
                                  onPressed: _next,
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: PtwSpacing.md),
                        ],
                      ),
                    ),
                  ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _composer() => Container(
    key: const ValueKey(ComponentIds.storyViewer),
    color: const Color(0xFF111218),
    child: Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: PtwSpacing.sm,
            vertical: PtwSpacing.xs,
          ),
          child: Row(
            children: [
              IconButton(
                key: const ValueKey(ComponentIds.storyViewerClose),
                onPressed: () => setState(() => _showComposer = false),
                icon: const Icon(
                  Icons.close_rounded,
                  color: PtwColors.textOnAccent,
                  size: 32,
                ),
              ),
              const Spacer(),
              Icon(
                SharePlatformStyle.icon(widget.guide.platform),
                color: PtwColors.textOnAccent,
              ),
              const SizedBox(width: PtwSpacing.xs),
              Text(
                widget.guide.platform.label,
                style: PtwTypography.bodyStrong.copyWith(
                  color: PtwColors.textOnAccent,
                ),
              ),
              const Spacer(),
              const SizedBox(width: 48),
            ],
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: PtwSpacing.lg),
            child: Image.memory(widget.asset.bytes, fit: BoxFit.contain),
          ),
        ),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(
            PtwSpacing.screenHorizontal,
            PtwSpacing.md,
            PtwSpacing.screenHorizontal,
            PtwSpacing.lg,
          ),
          decoration: const BoxDecoration(
            color: Color(0xFF1D1E24),
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(PtwRadius.xl),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Your card is ready',
                style: PtwTypography.title.copyWith(
                  color: PtwColors.textOnAccent,
                ),
              ),
              const SizedBox(height: PtwSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed:
                          () => _copy(widget.card.publicLink, 'Link copied'),
                      style: _composerButtonStyle(),
                      child: const Text('Copy link'),
                    ),
                  ),
                  const SizedBox(width: PtwSpacing.xs),
                  Expanded(
                    child: OutlinedButton(
                      onPressed:
                          () => _copy(widget.card.caption, 'Caption copied'),
                      style: _composerButtonStyle(),
                      child: const Text('Copy caption'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: PtwSpacing.sm),
              PtwBlackButton(
                label: 'Done',
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Future<void> _copy(String text, String message) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  ButtonStyle _composerButtonStyle() => OutlinedButton.styleFrom(
    foregroundColor: PtwColors.textOnAccent,
    side: const BorderSide(color: PtwColors.textOnAccent),
    minimumSize: const Size.fromHeight(46),
    shape: const StadiumBorder(),
  );
}

final class _PlatformRail extends StatelessWidget {
  const _PlatformRail({required this.selected});

  final SharePlatform selected;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      for (final platform in SharePlatform.values)
        AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: platform == selected ? 58 : 44,
          height: 44,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            color:
                platform == selected
                    ? PtwColors.surfacePrimary
                    : PtwColors.textOnAccent.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(PtwRadius.pill),
          ),
          child: Icon(
            SharePlatformStyle.icon(platform),
            size: 20,
            color:
                platform == selected
                    ? PtwColors.ink
                    : PtwColors.textOnAccent.withValues(alpha: 0.58),
          ),
        ),
    ],
  );
}

final class _GuideIllustration extends StatelessWidget {
  const _GuideIllustration({
    required this.kind,
    required this.platform,
    required this.link,
  });

  final String kind;
  final SharePlatform platform;
  final String link;

  @override
  Widget build(BuildContext context) => Container(
    height: 205,
    width: double.infinity,
    padding: const EdgeInsets.all(PtwSpacing.md),
    decoration: BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          SharePlatformStyle.color(platform).withValues(alpha: 0.86),
          PtwColors.ink,
        ],
      ),
      borderRadius: BorderRadius.circular(PtwRadius.lg),
    ),
    child: switch (kind) {
      'stickers' => _iconPanel(Icons.emoji_emotions_outlined, 'STICKERS'),
      'link' => _iconPanel(Icons.link_rounded, 'LINK'),
      'paste' => _linkPanel(),
      'frame' => _framePanel(),
      'crop' => _iconPanel(Icons.crop_rounded, 'KEEP FULL FRAME'),
      'caption' => _iconPanel(Icons.notes_rounded, 'PASTE CAPTION'),
      _ => _iconPanel(Icons.image_rounded, 'ADD CARD'),
    },
  );

  Widget _iconPanel(IconData icon, String label) => Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Container(
        width: 82,
        height: 82,
        decoration: const BoxDecoration(
          color: PtwColors.surfacePrimary,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: PtwColors.ink, size: 42),
      ),
      const SizedBox(height: PtwSpacing.sm),
      Text(
        label,
        style: PtwTypography.bodyStrong.copyWith(
          color: PtwColors.textOnAccent,
          letterSpacing: 1,
        ),
      ),
    ],
  );

  Widget _linkPanel() => Center(
    child: Container(
      padding: const EdgeInsets.symmetric(
        horizontal: PtwSpacing.md,
        vertical: PtwSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: PtwColors.surfacePrimary,
        borderRadius: BorderRadius.circular(PtwRadius.sm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.link_rounded, color: PtwColors.electricBlue),
          const SizedBox(width: PtwSpacing.xs),
          Flexible(
            child: Text(
              link.replaceFirst('https://', ''),
              overflow: TextOverflow.ellipsis,
              style: PtwTypography.bodyStrong.copyWith(
                color: PtwColors.electricBlue,
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _framePanel() => Stack(
    alignment: Alignment.center,
    children: [
      Container(
        width: 160,
        height: 150,
        decoration: BoxDecoration(
          color: PtwColors.textOnAccent.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(PtwRadius.lg),
        ),
      ),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: PtwColors.surfacePrimary,
          borderRadius: BorderRadius.circular(PtwRadius.sm),
        ),
        child: const Text('SEE THE JOURNEY →'),
      ),
    ],
  );
}
