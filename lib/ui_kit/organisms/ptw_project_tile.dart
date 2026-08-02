import 'package:flutter/material.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_gradients.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_project.dart';
import '../atoms/ptw_media_image.dart';

/// The canonical image-and-color representation of a PTW project.
final class PtwProjectTile extends StatelessWidget {
  const PtwProjectTile({
    required this.project,
    super.key,
    this.height = 310,
    this.onTap,
    this.compact = false,
  });

  final PtwProject project;
  final double height;
  final VoidCallback? onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final primary = Color(project.primaryColor);
    return Semantics(
      button: onTap != null,
      label: '${project.ownerName}: ${project.goal}',
      child: Material(
        key: const ValueKey(ComponentIds.projectTile),
        color: PtwColors.transparent,
        borderRadius: BorderRadius.circular(PtwRadius.xl),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: height,
            child: Stack(
              fit: StackFit.expand,
              children: [
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: PtwGradients.project(primary),
                  ),
                  child: PtwMediaImage(image: project.image),
                ),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: PtwGradients.projectImageOverlay(primary),
                  ),
                ),
                Padding(
                  padding: EdgeInsets.all(
                    compact ? PtwSpacing.md : PtwSpacing.lg,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          CircleAvatar(
                            radius: compact ? 17 : 20,
                            backgroundColor: PtwColors.surfacePrimary,
                            child: ClipOval(
                              child: Image.asset(
                                project.ownerAvatarAsset,
                                width: compact ? 31 : 36,
                                height: compact ? 31 : 36,
                                fit: BoxFit.cover,
                              ),
                            ),
                          ),
                          const SizedBox(width: PtwSpacing.xs),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  project.ownerName,
                                  style: PtwTypography.bodyStrong.copyWith(
                                    color: PtwColors.textOnAccent,
                                  ),
                                ),
                                Text(
                                  '@${project.ownerHandle}',
                                  style: PtwTypography.caption.copyWith(
                                    color: PtwColors.softWhite,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: PtwColors.ink.withValues(alpha: 0.48),
                              borderRadius: BorderRadius.circular(
                                PtwRadius.pill,
                              ),
                            ),
                            child: Text(
                              project.status == PtwProjectStatus.completed
                                  ? 'PROVED'
                                  : 'IN PROGRESS',
                              style: PtwTypography.caption.copyWith(
                                color: PtwColors.textOnAccent,
                                fontSize: 10,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 0.7,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const Spacer(),
                      Text(
                        project.goal,
                        maxLines: compact ? 3 : 4,
                        overflow: TextOverflow.ellipsis,
                        style: (compact
                                ? PtwTypography.titleLarge
                                : PtwTypography.display)
                            .copyWith(color: PtwColors.textOnAccent),
                      ),
                      const SizedBox(height: PtwSpacing.sm),
                      Row(
                        children: [
                          const Icon(
                            Icons.flag_rounded,
                            color: PtwColors.textOnAccent,
                            size: 18,
                          ),
                          const SizedBox(width: PtwSpacing.xs),
                          Text(
                            PtwFormatters.deadline(project.deadline),
                            style: PtwTypography.bodyStrong.copyWith(
                              color: PtwColors.textOnAccent,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
