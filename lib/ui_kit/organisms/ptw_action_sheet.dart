import 'package:flutter/material.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../atoms/ptw_sticker_text.dart';

final class PtwActionSheetItem<T> {
  const PtwActionSheetItem({
    required this.id,
    required this.label,
    required this.value,
    this.isDestructive = false,
  });

  final String id;
  final String label;
  final T value;
  final bool isDestructive;
}

Future<T?> showPtwActionSheet<T>(
  BuildContext context, {
  required List<PtwActionSheetItem<T>> actions,
  Color accentColor = PtwColors.hotPink,
}) => showModalBottomSheet<T>(
  context: context,
  backgroundColor: PtwColors.transparent,
  barrierColor: PtwColors.overlay,
  isScrollControlled: true,
  builder:
      (context) =>
          _PtwActionSheet<T>(actions: actions, accentColor: accentColor),
);

final class _PtwActionSheet<T> extends StatelessWidget {
  const _PtwActionSheet({required this.actions, required this.accentColor});

  final List<PtwActionSheetItem<T>> actions;
  final Color accentColor;

  @override
  Widget build(BuildContext context) => Container(
    key: const ValueKey(ComponentIds.actionSheet),
    margin: const EdgeInsets.all(PtwSpacing.sm),
    padding: const EdgeInsets.all(PtwSpacing.md),
    decoration: BoxDecoration(
      color: PtwColors.ink,
      border: Border.all(color: PtwColors.textOnAccent, width: 1),
      borderRadius: BorderRadius.circular(PtwRadius.xl),
    ),
    child: SafeArea(
      top: false,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var index = 0; index < actions.length; index++) ...[
            TextButton(
              key: ValueKey(actions[index].id),
              onPressed: () => Navigator.pop(context, actions[index].value),
              style: TextButton.styleFrom(
                minimumSize: Size.fromHeight(index == 0 ? 68 : 54),
                alignment: Alignment.centerLeft,
                foregroundColor:
                    actions[index].isDestructive
                        ? PtwColors.flame
                        : PtwColors.textOnAccent,
                padding: const EdgeInsets.symmetric(
                  horizontal: PtwSpacing.sm,
                  vertical: PtwSpacing.xs,
                ),
              ),
              child:
                  index == 0
                      ? PtwStickerText.actionSheet(
                        actions[index].label,
                        accentColor:
                            actions[index].isDestructive
                                ? PtwColors.flame
                                : accentColor,
                      )
                      : Text(
                        actions[index].label,
                        style: PtwTypography.title.copyWith(
                          color:
                              actions[index].isDestructive
                                  ? PtwColors.flame
                                  : PtwColors.textOnAccent,
                        ),
                      ),
            ),
            if (index != actions.length - 1)
              const SizedBox(height: PtwSpacing.xxs),
          ],
        ],
      ),
    ),
  );
}
