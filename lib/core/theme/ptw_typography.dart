import 'package:flutter/material.dart';

import 'ptw_colors.dart';

/// PTW typography primitives.
abstract final class PtwTypography {
  static const _family = 'PtwRoboto';
  static const display = TextStyle(
    fontFamily: _family,
    fontSize: 38,
    height: 1.0,
    fontWeight: FontWeight.w900,
    color: PtwColors.textPrimary,
  );
  static const titleLarge = TextStyle(
    fontFamily: _family,
    fontSize: 28,
    height: 1.05,
    fontWeight: FontWeight.w900,
    color: PtwColors.textPrimary,
  );
  static const title = TextStyle(
    fontFamily: _family,
    fontSize: 20,
    height: 1.2,
    fontWeight: FontWeight.w900,
    color: PtwColors.textPrimary,
  );
  static const body = TextStyle(
    fontFamily: _family,
    fontSize: 16,
    height: 1.4,
    fontWeight: FontWeight.w400,
    color: PtwColors.textPrimary,
  );
  static const bodyStrong = TextStyle(
    fontFamily: _family,
    fontSize: 15,
    height: 1.3,
    fontWeight: FontWeight.w700,
    color: PtwColors.textPrimary,
  );
  static const caption = TextStyle(
    fontFamily: _family,
    fontSize: 12,
    height: 1.3,
    color: PtwColors.textSecondary,
  );
  static const label = TextStyle(
    fontFamily: _family,
    fontSize: 14,
    height: 1.2,
    fontWeight: FontWeight.w700,
    color: PtwColors.textPrimary,
  );
  static const button = TextStyle(
    fontFamily: _family,
    fontSize: 16,
    height: 1.1,
    fontWeight: FontWeight.w900,
  );
  static const storyHeadline = TextStyle(
    fontFamily: _family,
    fontSize: 30,
    height: 1.04,
    fontWeight: FontWeight.w800,
    color: PtwColors.textOnAccent,
  );
}
