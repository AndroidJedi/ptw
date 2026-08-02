import 'package:flutter/material.dart';

import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_response.dart';

/// Direct, full-message response presentation shared by Home and Inbox.
final class PtwResponseContent extends StatelessWidget {
  const PtwResponseContent({
    required this.response,
    super.key,
    this.framed = false,
    this.padding = const EdgeInsets.all(PtwSpacing.lg),
  });

  final PtwResponse response;
  final bool framed;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final content = Padding(
      padding: padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            response.side == PtwResponseSide.believe
                ? 'THEY BELIEVE'
                : 'THEY DOUBT',
            style: PtwTypography.caption.copyWith(
              color: PtwColors.textOnAccent,
              fontWeight: FontWeight.w900,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: PtwSpacing.sm),
          Text(
            response.message,
            style: PtwTypography.titleLarge.copyWith(
              color: PtwColors.textOnAccent,
            ),
          ),
          const SizedBox(height: PtwSpacing.lg),
          Text(
            'Anonymous · ${PtwFormatters.relative(response.createdAt)}',
            style: PtwTypography.bodyStrong.copyWith(
              color: PtwColors.softWhite,
            ),
          ),
        ],
      ),
    );
    if (!framed) return content;
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: PtwColors.hotPink,
        border: Border.all(color: PtwColors.textOnAccent, width: 1),
        borderRadius: BorderRadius.circular(PtwRadius.xl),
      ),
      child: content,
    );
  }
}
