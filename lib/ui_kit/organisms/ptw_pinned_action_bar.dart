import 'package:flutter/material.dart';

import '../../core/theme/ptw_spacing.dart';

final class PtwPinnedActionBar extends StatelessWidget {
  const PtwPinnedActionBar({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      PtwSpacing.screenHorizontal,
      PtwSpacing.xs,
      PtwSpacing.screenHorizontal,
      PtwSpacing.md,
    ),
    child: child,
  );
}
