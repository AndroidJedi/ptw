import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class ShareStoryPreviewScreen extends StatelessWidget {
  const ShareStoryPreviewScreen({required this.projectId, super.key});

  final String projectId;

  void _prepared(BuildContext context, String platform) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Project card prepared for $platform')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(projectId);
    if (project == null) {
      return PtwImmersivePage(
        child: Column(
          children: [
            const Align(
              alignment: Alignment.centerLeft,
              child: PtwBackButton(fallbackRoute: '/'),
            ),
            Expanded(
              child: Center(
                child: Text(
                  'Project unavailable',
                  style: PtwTypography.titleLarge.copyWith(
                    color: PtwColors.textOnAccent,
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }
    final link = 'https://ptw.to/${project.ownerHandle}';
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.shareScreen),
      child: Column(
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: PtwBackButton(
              key: ValueKey(ComponentIds.shareBack),
              fallbackRoute: '/',
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PtwSpacing.screenHorizontal,
                PtwSpacing.xs,
                PtwSpacing.screenHorizontal,
                PtwSpacing.xxl,
              ),
              children: [
                PtwProjectTile(project: project, height: 410),
                const SizedBox(height: PtwSpacing.md),
                OutlinedButton.icon(
                  key: const ValueKey(ComponentIds.shareCopyLink),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: link));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Link copied')),
                    );
                  },
                  icon: const Icon(Icons.link_rounded),
                  label: Text(
                    'PTW.TO/${project.ownerHandle.toUpperCase()}',
                    overflow: TextOverflow.ellipsis,
                  ),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size.fromHeight(56),
                    foregroundColor: PtwColors.textOnAccent,
                    side: const BorderSide(
                      color: PtwColors.textOnAccent,
                      width: 1,
                    ),
                    textStyle: PtwTypography.bodyStrong,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(PtwRadius.lg),
                    ),
                  ),
                ),
                const SizedBox(height: PtwSpacing.sm),
                PtwBlackButton(
                  label: 'Share to Stories',
                  icon: Icons.auto_awesome_rounded,
                  onPressed: () => _prepared(context, 'Stories'),
                ),
                const SizedBox(height: PtwSpacing.sm),
                Row(
                  children: [
                    Expanded(
                      child: _ShareAction(
                        icon: Icons.camera_alt_rounded,
                        label: 'Instagram',
                        onTap: () => _prepared(context, 'Instagram'),
                      ),
                    ),
                    const SizedBox(width: PtwSpacing.xs),
                    Expanded(
                      child: _ShareAction(
                        icon: Icons.music_note_rounded,
                        label: 'TikTok',
                        onTap: () => _prepared(context, 'TikTok'),
                      ),
                    ),
                    const SizedBox(width: PtwSpacing.xs),
                    Expanded(
                      child: _ShareAction(
                        icon: Icons.more_horiz_rounded,
                        label: 'More',
                        onTap: () => _prepared(context, 'other apps'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

final class _ShareAction extends StatelessWidget {
  const _ShareAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => OutlinedButton(
    onPressed: onTap,
    style: OutlinedButton.styleFrom(
      minimumSize: const Size.fromHeight(70),
      padding: const EdgeInsets.symmetric(horizontal: PtwSpacing.xs),
      foregroundColor: PtwColors.textOnAccent,
      side: const BorderSide(color: PtwColors.textOnAccent, width: 1),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PtwRadius.lg),
      ),
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon),
        const SizedBox(height: PtwSpacing.xxs),
        Text(
          label,
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    ),
  );
}
