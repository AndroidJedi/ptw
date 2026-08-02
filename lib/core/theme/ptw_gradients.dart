import 'package:flutter/material.dart';

import 'ptw_colors.dart';

/// Reusable PTW gradients.
abstract final class PtwGradients {
  static LinearGradient project(Color primary) => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color.lerp(primary, PtwColors.surfacePrimary, 0.10)!,
      primary,
      Color.lerp(primary, PtwColors.ink, 0.15)!,
    ],
  );

  static LinearGradient projectImageOverlay(Color primary) => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    stops: const [0, 0.42, 1],
    colors: [
      const Color(0x18000000),
      primary.withValues(alpha: 0.36),
      Color.lerp(primary, PtwColors.ink, 0.28)!.withValues(alpha: 0.94),
    ],
  );

  static const primary = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [PtwColors.accentPurple, PtwColors.accentPink],
  );
  static const share = LinearGradient(
    colors: [PtwColors.accentPink, PtwColors.accentCoral],
  );
  static const soft = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [PtwColors.surfaceLavender, PtwColors.surfacePeach],
  );
  static const storyFallback = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [PtwColors.accentBlue, PtwColors.accentPink],
  );
  static const storyOverlay = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [PtwColors.transparent, PtwColors.overlay],
  );
  static const heroOverlay = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    stops: [0, 0.46, 1],
    colors: [Color(0x1A000000), Color(0x42000000), Color(0xE617132A)],
  );
  static const believe = LinearGradient(
    colors: [PtwColors.accentPurple, PtwColors.accentBlue],
  );
}
