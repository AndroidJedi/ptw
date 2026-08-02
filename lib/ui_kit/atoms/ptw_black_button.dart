import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import 'ptw_sticker_text.dart';

final class PtwBlackButton extends StatelessWidget {
  const PtwBlackButton({
    required this.label,
    required this.onPressed,
    super.key,
    this.icon,
    this.accentColor = PtwColors.hotPink,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Color accentColor;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: double.infinity,
    height: 58,
    child: FilledButton.icon(
      onPressed: onPressed,
      icon: icon == null ? const SizedBox.shrink() : Icon(icon, size: 20),
      label: PtwStickerText.action(
        label,
        accentColor: accentColor,
        enabled: onPressed != null,
      ),
      style: FilledButton.styleFrom(
        backgroundColor: PtwColors.ink,
        disabledBackgroundColor: PtwColors.ink,
        foregroundColor: PtwColors.textOnAccent,
        disabledForegroundColor: PtwColors.textOnAccent.withValues(alpha: 0.62),
        side: const BorderSide(color: PtwColors.textOnAccent, width: 1),
        shape: const StadiumBorder(),
        elevation: 7,
        shadowColor: PtwColors.ink.withValues(alpha: 0.32),
      ),
    ),
  );
}
