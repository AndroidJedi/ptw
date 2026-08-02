import 'package:flutter/material.dart';

import 'ptw_colors.dart';
import 'ptw_radius.dart';
import 'ptw_typography.dart';

/// Light PTW application theme assembled from design tokens.
abstract final class PtwTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: PtwColors.accentPurple,
      brightness: Brightness.light,
      surface: PtwColors.surfacePrimary,
    );
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'PtwRoboto',
      colorScheme: scheme,
      scaffoldBackgroundColor: PtwColors.paper,
      textTheme: const TextTheme(
        headlineLarge: PtwTypography.display,
        headlineMedium: PtwTypography.titleLarge,
        titleLarge: PtwTypography.title,
        bodyLarge: PtwTypography.body,
        bodyMedium: PtwTypography.body,
        labelLarge: PtwTypography.button,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: PtwColors.paper,
        foregroundColor: PtwColors.textPrimary,
        surfaceTintColor: PtwColors.transparent,
        centerTitle: true,
        elevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: PtwColors.surfacePrimary,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(PtwRadius.md),
          borderSide: const BorderSide(color: PtwColors.borderDefault),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(PtwRadius.md),
          borderSide: const BorderSide(color: PtwColors.borderDefault),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(PtwRadius.md),
          borderSide: const BorderSide(color: PtwColors.borderAccent),
        ),
      ),
    );
  }
}
