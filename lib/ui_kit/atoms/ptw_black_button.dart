import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import 'ptw_sticker_text.dart';

final class PtwBlackButton extends StatelessWidget {
  const PtwBlackButton({
    required this.label,
    required this.onPressed,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: double.infinity,
    height: 58,
    child: FilledButton(
      onPressed: onPressed,
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
      child: PtwStickerText.action(label, enabled: onPressed != null),
    ),
  );
}
