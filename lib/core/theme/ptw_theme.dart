import 'package:flutter/material.dart';

import 'ptw_colors.dart';
import 'ptw_radius.dart';
import 'ptw_typography.dart';

/// Light PTW application theme assembled from design tokens.
abstract final class PtwTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: PtwColors.hotPink,
      brightness: Brightness.light,
      surface: PtwColors.surfacePrimary,
    );
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'PtwRoboto',
      colorScheme: scheme,
      scaffoldBackgroundColor: PtwColors.hotPink,
      textTheme: const TextTheme(
        headlineLarge: PtwTypography.display,
        headlineMedium: PtwTypography.titleLarge,
        titleLarge: PtwTypography.title,
        bodyLarge: PtwTypography.body,
        bodyMedium: PtwTypography.body,
        labelLarge: PtwTypography.button,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: PtwColors.hotPink,
        foregroundColor: PtwColors.textOnAccent,
        surfaceTintColor: PtwColors.transparent,
        centerTitle: true,
        elevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: PtwColors.surfacePrimary,
        counterStyle: const TextStyle(color: PtwColors.softWhite),
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
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: PtwColors.ink,
        contentTextStyle: TextStyle(
          color: PtwColors.textOnAccent,
          fontWeight: FontWeight.w700,
        ),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
