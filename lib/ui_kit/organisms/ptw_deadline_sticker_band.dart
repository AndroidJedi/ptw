import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../atoms/ptw_finish_flag_icon.dart';
import '../atoms/ptw_sticker_text.dart';

/// A shallow interstitial that turns the deadline into an immediate signal.
final class PtwDeadlineStickerBand extends StatelessWidget {
  const PtwDeadlineStickerBand({
    required this.daysRemaining,
    this.completed = false,
    super.key,
  });

  final int daysRemaining;
  final bool completed;

  String get _primaryInfo {
    if (completed) return 'DONE';
    if (daysRemaining < 0) return '${-daysRemaining}';
    if (daysRemaining == 0) return 'TODAY';
    return '$daysRemaining';
  }

  String? get _secondaryInfo {
    if (completed || daysRemaining == 0) return null;
    if (daysRemaining < 0) {
      return daysRemaining == -1 ? 'DAY LATE' : 'DAYS LATE';
    }
    return daysRemaining == 1 ? 'DAY LEFT' : 'DAYS LEFT';
  }

  String get _semanticLabel {
    if (completed) return 'PTW. Project finished';
    if (daysRemaining < 0) {
      final days = -daysRemaining;
      return 'PTW. $days ${days == 1 ? 'day' : 'days'} late';
    }
    if (daysRemaining == 0) return 'PTW. Due today';
    return 'PTW. $daysRemaining ${daysRemaining == 1 ? 'day' : 'days'} left';
  }

  @override
  Widget build(BuildContext context) => Semantics(
    key: const ValueKey(ComponentIds.projectDeadlineBand),
    label: _semanticLabel,
    excludeSemantics: true,
    child: SizedBox(
      width: double.infinity,
      height: 126,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: PtwSpacing.screenHorizontal,
          vertical: PtwSpacing.md,
        ),
        child: Row(
          children: [
            Transform.rotate(
              angle: -5 * math.pi / 180,
              child: Container(
                key: const ValueKey(ComponentIds.projectDeadlineSticker),
                padding: const EdgeInsets.fromLTRB(18, 13, 18, 14),
                decoration: BoxDecoration(
                  color: PtwColors.ink,
                  border: Border.all(color: PtwColors.textOnAccent, width: 2),
                  borderRadius: BorderRadius.circular(17),
                  boxShadow: [
                    BoxShadow(
                      color: PtwColors.ink.withValues(alpha: 0.38),
                      offset: const Offset(6, 7),
                    ),
                  ],
                ),
                child: const PtwStickerText.brand('PTW'),
              ),
            ),
            const SizedBox(width: PtwSpacing.xl),
            const PtwFinishFlagIcon(size: 22),
            const SizedBox(width: PtwSpacing.sm),
            Column(
              key: const ValueKey(ComponentIds.projectDeadlineDays),
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _primaryInfo,
                  style: PtwTypography.display.copyWith(
                    color: PtwColors.textOnAccent,
                    fontSize: 42,
                    height: 0.9,
                  ),
                ),
                if (_secondaryInfo case final secondary?) ...[
                  const SizedBox(height: PtwSpacing.xxs),
                  Text(
                    secondary,
                    style: PtwTypography.caption.copyWith(
                      color: PtwColors.textOnAccent,
                      fontSize: 10,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.2,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
