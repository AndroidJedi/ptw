import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_gradients.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
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
      return const Scaffold(body: Center(child: Text('Project not found')));
    }
    final primary = Color(project.primaryColor);
    final link = 'https://ptw.to/${project.ownerHandle}';
    return Scaffold(
      key: const ValueKey(ComponentIds.shareScreen),
      body: DecoratedBox(
        decoration: BoxDecoration(gradient: PtwGradients.project(primary)),
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: [
              Row(
                children: [
                  IconButton.filled(
                    onPressed: () => context.go('/'),
                    style: IconButton.styleFrom(
                      backgroundColor: PtwColors.softWhite,
                      foregroundColor: PtwColors.ink,
                    ),
                    icon: const Icon(Icons.close_rounded),
                  ),
                  const Spacer(),
                  Text(
                    'READY TO SHARE',
                    style: PtwTypography.caption.copyWith(
                      color: PtwColors.textOnAccent,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const Spacer(),
                  const SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: PtwSpacing.md),
              Center(
                child: SizedBox(
                  width: 310,
                  child: PtwProjectTile(project: project, height: 450),
                ),
              ),
              const SizedBox(height: PtwSpacing.md),
              Container(
                padding: const EdgeInsets.all(PtwSpacing.md),
                decoration: BoxDecoration(
                  color: PtwColors.softWhite,
                  borderRadius: BorderRadius.circular(PtwRadius.lg),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'PTW.TO/${project.ownerHandle.toUpperCase()}',
                        overflow: TextOverflow.ellipsis,
                        style: PtwTypography.bodyStrong,
                      ),
                    ),
                    IconButton.filled(
                      key: const ValueKey(ComponentIds.shareCopyLink),
                      tooltip: 'Copy link',
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: link));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Link copied')),
                        );
                      },
                      style: IconButton.styleFrom(
                        backgroundColor: PtwColors.ink,
                      ),
                      icon: const Icon(
                        Icons.link_rounded,
                        color: PtwColors.textOnAccent,
                      ),
                    ),
                  ],
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
                    child: _ShareChip(
                      icon: Icons.camera_alt_rounded,
                      label: 'Instagram',
                      onTap: () => _prepared(context, 'Instagram'),
                    ),
                  ),
                  const SizedBox(width: PtwSpacing.xs),
                  Expanded(
                    child: _ShareChip(
                      icon: Icons.music_note_rounded,
                      label: 'TikTok',
                      onTap: () => _prepared(context, 'TikTok'),
                    ),
                  ),
                  const SizedBox(width: PtwSpacing.xs),
                  Expanded(
                    child: _ShareChip(
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
      ),
    );
  }
}

final class _ShareChip extends StatelessWidget {
  const _ShareChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: PtwColors.softWhite,
    borderRadius: BorderRadius.circular(PtwRadius.lg),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(PtwRadius.lg),
      child: SizedBox(
        height: 72,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon),
            const SizedBox(height: 4),
            Text(
              label,
              style: PtwTypography.caption.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
