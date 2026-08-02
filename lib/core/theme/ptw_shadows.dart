import 'package:flutter/material.dart';

import 'ptw_colors.dart';

/// Reusable elevation treatments.
abstract final class PtwShadows {
  static const soft = [
    BoxShadow(color: PtwColors.shadow, blurRadius: 24, offset: Offset(0, 10)),
  ];
}
