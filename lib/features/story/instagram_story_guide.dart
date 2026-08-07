import 'dart:ui';

import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';

enum InstagramGuideShareStatus { success, dismissed, unavailable, failed }

final class InstagramGuideShareResult {
  const InstagramGuideShareResult(this.status, {this.message});

  final InstagramGuideShareStatus status;
  final String? message;
}

Future<bool> showInstagramStoryGuide({
  required BuildContext context,
  required Future<InstagramGuideShareResult> Function(Rect origin) onShare,
  required Future<bool> Function() onCopy,
}) async =>
    await showGeneralDialog<bool>(
      context: context,
      barrierDismissible: false,
      barrierLabel: 'Instagram Story guide',
      barrierColor: PtwColors.ink.withValues(alpha: 0.42),
      transitionDuration: const Duration(milliseconds: 220),
      pageBuilder:
          (_, __, ___) =>
              _InstagramStoryGuide(onShare: onShare, onCopy: onCopy),
      transitionBuilder:
          (_, animation, __, child) => FadeTransition(
            opacity: CurvedAnimation(parent: animation, curve: Curves.easeOut),
            child: ScaleTransition(
              scale: Tween(begin: 0.96, end: 1.0).animate(animation),
              child: child,
            ),
          ),
    ) ??
    false;

final class _InstagramStoryGuide extends StatefulWidget {
  const _InstagramStoryGuide({required this.onShare, required this.onCopy});

  final Future<InstagramGuideShareResult> Function(Rect origin) onShare;
  final Future<bool> Function() onCopy;

  @override
  State<_InstagramStoryGuide> createState() => _InstagramStoryGuideState();
}

final class _InstagramStoryGuideState extends State<_InstagramStoryGuide> {
  final _shareKey = GlobalKey();
  var _step = 0;
  var _busy = false;
  String? _message;
  var _showCopy = false;

  Rect get _shareOrigin {
    final box = _shareKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return const Rect.fromLTWH(0, 0, 1, 1);
    return box.localToGlobal(Offset.zero) & box.size;
  }

  Future<void> _next() async {
    if (_busy) return;
    if (_step < 3) {
      setState(() {
        _step++;
        _message = null;
      });
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
      _showCopy = false;
    });
    final result = await widget.onShare(_shareOrigin);
    if (!mounted) return;
    if (result.status == InstagramGuideShareStatus.success) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _busy = false;
      _showCopy = result.status != InstagramGuideShareStatus.dismissed;
      _message =
          result.message ??
          switch (result.status) {
            InstagramGuideShareStatus.dismissed =>
              'Share sheet closed. Your Story is still here.',
            InstagramGuideShareStatus.unavailable =>
              'Sharing is unavailable on this device.',
            InstagramGuideShareStatus.failed =>
              'Could not prepare the Story. Try again.',
            InstagramGuideShareStatus.success => null,
          };
    });
  }

  Future<void> _copyAgain() async {
    if (_busy) return;
    setState(() => _busy = true);
    final copied = await widget.onCopy();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _message = copied ? 'PTW link copied.' : 'The link could not be copied.';
    });
  }

  @override
  Widget build(BuildContext context) {
    final item = _steps[_step];
    return Material(
      color: PtwColors.transparent,
      child: Stack(
        children: [
          Positioned.fill(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
              child: const ColoredBox(color: PtwColors.transparent),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 10, 18, 18),
              child: Column(
                children: [
                  Align(
                    alignment: Alignment.centerRight,
                    child: IconButton.filledTonal(
                      key: const ValueKey('instagram_guide_close'),
                      onPressed:
                          _busy ? null : () => Navigator.of(context).pop(false),
                      icon: const Icon(Icons.close),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Expanded(
                    child: Center(
                      child: Container(
                        constraints: const BoxConstraints(maxWidth: 500),
                        padding: const EdgeInsets.fromLTRB(22, 24, 22, 20),
                        decoration: BoxDecoration(
                          color: PtwColors.surfacePrimary,
                          borderRadius: BorderRadius.circular(34),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x3D000000),
                              blurRadius: 32,
                              offset: Offset(0, 16),
                            ),
                          ],
                        ),
                        child: Column(
                          children: [
                            const _InstagramPill(),
                            const SizedBox(height: 18),
                            const Text(
                              'Add your PTW link',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontFamily: 'PtwLilitaOne',
                                fontSize: 30,
                                height: 0.95,
                                color: PtwColors.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 16),
                            _ProgressDots(step: _step),
                            const SizedBox(height: 18),
                            Text(
                              item.instruction,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                fontSize: 21,
                                height: 1.08,
                                fontWeight: FontWeight.w900,
                                color: PtwColors.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 18),
                            Expanded(
                              child: AnimatedSwitcher(
                                duration: const Duration(milliseconds: 180),
                                child: KeyedSubtree(
                                  key: ValueKey(_step),
                                  child: item.illustration,
                                ),
                              ),
                            ),
                            if (_message != null) ...[
                              const SizedBox(height: 10),
                              Text(
                                _message!,
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  color: PtwColors.textSecondary,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                            if (_showCopy)
                              TextButton.icon(
                                onPressed: _busy ? null : _copyAgain,
                                icon: const Icon(Icons.link),
                                label: const Text('Copy link'),
                              ),
                            const SizedBox(height: 12),
                            SizedBox(
                              key: _shareKey,
                              width: double.infinity,
                              height: 58,
                              child: FilledButton(
                                key: ValueKey(
                                  'instagram_guide_next_${_step + 1}',
                                ),
                                onPressed: _busy ? null : _next,
                                style: FilledButton.styleFrom(
                                  backgroundColor: PtwColors.ink,
                                  foregroundColor: PtwColors.textOnAccent,
                                  shape: const StadiumBorder(),
                                ),
                                child:
                                    _busy
                                        ? const SizedBox.square(
                                          dimension: 22,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2.5,
                                            color: PtwColors.textOnAccent,
                                          ),
                                        )
                                        : Text(
                                          _step == 3
                                              ? 'Share Story'
                                              : 'Next Step',
                                          style: const TextStyle(
                                            fontSize: 18,
                                            fontWeight: FontWeight.w900,
                                          ),
                                        ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

final class _GuideStep {
  const _GuideStep(this.instruction, this.illustration);

  final String instruction;
  final Widget illustration;
}

const _steps = <_GuideStep>[
  _GuideStep('Open Instagram’s sticker tray.', _StickerTrayIllustration()),
  _GuideStep('Choose the Link sticker.', _ChooseLinkIllustration()),
  _GuideStep('Paste your copied PTW link.', _PasteLinkIllustration()),
  _GuideStep('Keep the link clear of your goal.', _FrameLinkIllustration()),
];

final class _InstagramPill extends StatelessWidget {
  const _InstagramPill();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
    decoration: const BoxDecoration(
      color: PtwColors.surfaceMuted,
      borderRadius: BorderRadius.all(Radius.circular(999)),
    ),
    child: const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.camera_alt_outlined, size: 21),
        SizedBox(width: 8),
        Text('Instagram Story', style: TextStyle(fontWeight: FontWeight.w900)),
      ],
    ),
  );
}

final class _ProgressDots extends StatelessWidget {
  const _ProgressDots({required this.step});

  final int step;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      for (var index = 0; index < 4; index++) ...[
        AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          width: 32,
          height: 32,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: index == step ? PtwColors.ink : PtwColors.surfaceMuted,
            shape: BoxShape.circle,
          ),
          child: Text(
            '${index + 1}',
            style: TextStyle(
              color:
                  index == step
                      ? PtwColors.textOnAccent
                      : PtwColors.textPrimary,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        if (index != 3) const SizedBox(width: 8),
      ],
    ],
  );
}

final class _PhoneCanvas extends StatelessWidget {
  const _PhoneCanvas({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Center(
    child: AspectRatio(
      aspectRatio: 1.38,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF7257FF), Color(0xFFF4066E), Color(0xFFFF8A00)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
        ),
        child: child,
      ),
    ),
  );
}

final class _StickerTrayIllustration extends StatelessWidget {
  const _StickerTrayIllustration();

  @override
  Widget build(BuildContext context) => _PhoneCanvas(
    child: Column(
      children: [
        const Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            CircleAvatar(child: Text('Aa')),
            SizedBox(width: 8),
            CircleAvatar(
              backgroundColor: PtwColors.textOnAccent,
              child: Icon(Icons.emoji_emotions_outlined, color: PtwColors.ink),
            ),
          ],
        ),
        const Spacer(),
        Transform.rotate(
          angle: -0.15,
          child: const Icon(
            Icons.back_hand_outlined,
            color: PtwColors.textOnAccent,
            size: 82,
          ),
        ),
      ],
    ),
  );
}

final class _ChooseLinkIllustration extends StatelessWidget {
  const _ChooseLinkIllustration();

  @override
  Widget build(BuildContext context) => _PhoneCanvas(
    child: GridView.count(
      crossAxisCount: 3,
      physics: const NeverScrollableScrollPhysics(),
      children: const [
        _StickerTile(icon: Icons.poll_outlined, label: 'POLL'),
        _StickerTile(icon: Icons.alternate_email, label: 'MENTION'),
        _StickerTile(icon: Icons.tag, label: 'HASHTAG'),
        _StickerTile(icon: Icons.timer_outlined, label: 'COUNTDOWN'),
        _StickerTile(icon: Icons.link, label: 'LINK', highlighted: true),
        _StickerTile(icon: Icons.music_note, label: 'MUSIC'),
      ],
    ),
  );
}

final class _StickerTile extends StatelessWidget {
  const _StickerTile({
    required this.icon,
    required this.label,
    this.highlighted = false,
  });

  final IconData icon;
  final String label;
  final bool highlighted;

  @override
  Widget build(BuildContext context) => Center(
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
      decoration: BoxDecoration(
        color: PtwColors.textOnAccent,
        borderRadius: BorderRadius.circular(8),
        border:
            highlighted
                ? Border.all(color: PtwColors.electricBlue, width: 4)
                : null,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: PtwColors.ink, size: 20),
          Text(
            label,
            style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w900),
          ),
        ],
      ),
    ),
  );
}

final class _PasteLinkIllustration extends StatelessWidget {
  const _PasteLinkIllustration();

  @override
  Widget build(BuildContext context) => _PhoneCanvas(
    child: Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: PtwColors.surfacePrimary,
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'Add link',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          SizedBox(height: 14),
          DecoratedBox(
            decoration: BoxDecoration(
              color: PtwColors.surfaceMuted,
              borderRadius: BorderRadius.all(Radius.circular(10)),
            ),
            child: Padding(
              padding: EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(child: Text('https://ptw.to/p/you')),
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: PtwColors.ink,
                      borderRadius: BorderRadius.all(Radius.circular(8)),
                    ),
                    child: Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 7,
                      ),
                      child: Text(
                        'PASTE',
                        style: TextStyle(
                          color: PtwColors.textOnAccent,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

final class _FrameLinkIllustration extends StatelessWidget {
  const _FrameLinkIllustration();

  @override
  Widget build(BuildContext context) => _PhoneCanvas(
    child: Stack(
      children: [
        const Align(
          alignment: Alignment(0, -0.35),
          child: Text(
            'I WILL\nPROVE IT.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: 'PtwLilitaOne',
              color: PtwColors.textOnAccent,
              fontSize: 30,
              height: 0.9,
            ),
          ),
        ),
        Align(
          alignment: const Alignment(0, 0.72),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
            decoration: BoxDecoration(
              color: PtwColors.textOnAccent,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.link, color: PtwColors.electricBlue),
                SizedBox(width: 6),
                Text(
                  'PTW.TO',
                  style: TextStyle(
                    color: PtwColors.electricBlue,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}
