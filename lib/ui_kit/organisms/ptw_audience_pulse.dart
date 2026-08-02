import 'package:flutter/material.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_reaction_summary.dart';

final class PtwAudiencePulse extends StatelessWidget {
  const PtwAudiencePulse({required this.summary, super.key});

  final PtwReactionSummary summary;

  @override
  Widget build(BuildContext context) {
    if (summary.total == 0) return const SizedBox.shrink();
    return Semantics(
      excludeSemantics: true,
      label: '${summary.believe} believe, ${summary.doubt} doubt',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text(
                '${summary.believe} BELIEVE',
                style: PtwTypography.caption.copyWith(
                  color: PtwColors.textOnAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 10,
                ),
              ),
              const Spacer(),
              Text(
                '${summary.doubt} DOUBT',
                style: PtwTypography.caption.copyWith(
                  color: PtwColors.textOnAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 10,
                ),
              ),
            ],
          ),
          const SizedBox(height: PtwSpacing.xxs),
          Container(
            key: const ValueKey(ComponentIds.projectAudienceMeter),
            height: 7,
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: PtwColors.ink,
              border: Border.all(color: PtwColors.textOnAccent, width: 1),
              borderRadius: BorderRadius.circular(999),
            ),
            alignment: Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: summary.believeFraction,
              heightFactor: 1,
              child: const ColoredBox(color: PtwColors.textOnAccent),
            ),
          ),
        ],
      ),
    );
  }
}
