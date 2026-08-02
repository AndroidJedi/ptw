import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';

final class PtwBackButton extends StatelessWidget {
  const PtwBackButton({
    required this.fallbackRoute,
    super.key,
    this.onPressed,
    this.color = PtwColors.textOnAccent,
  });

  final String fallbackRoute;
  final VoidCallback? onPressed;
  final Color color;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: 'Back',
    onPressed:
        onPressed ??
        () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go(fallbackRoute);
          }
        },
    padding: const EdgeInsets.all(PtwSpacing.sm),
    icon: Icon(Icons.arrow_back_ios_new_rounded, color: color, size: 24),
  );
}
