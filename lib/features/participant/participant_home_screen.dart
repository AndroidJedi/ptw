import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_image_ref.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class ParticipantHomeScreen extends StatelessWidget {
  const ParticipantHomeScreen({super.key});

  Future<void> _reset(BuildContext context, PtwAppState state) async {
    final approved = await showDialog<bool>(
      context: context,
      builder:
          (context) => AlertDialog(
            title: const Text('Reset prototype?'),
            content: const Text('Replace local changes with the seed data?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Reset'),
              ),
            ],
          ),
    );
    if (approved == true) await state.reset();
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.currentProject;
    final proof = state.evidenceFor(project.id);
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.projectHome),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
          PtwSpacing.screenHorizontal,
          PtwSpacing.sm,
          PtwSpacing.screenHorizontal,
          PtwSpacing.xxl,
        ),
        children: [
          PtwProjectTile(project: project, height: 330),
          const SizedBox(height: PtwSpacing.md),
          PtwBlackButton(
            key: const ValueKey(ComponentIds.projectShare),
            label: 'Share project',
            icon: Icons.ios_share_rounded,
            onPressed: () => context.push('/projects/${project.id}/share'),
          ),
          const SizedBox(height: PtwSpacing.sm),
          Row(
            children: [
              Expanded(
                child: _HubAction(
                  key: const ValueKey(ComponentIds.projectInbox),
                  icon: Icons.inbox_rounded,
                  label:
                      state.unreadResponseCount == 0
                          ? 'Inbox'
                          : 'Inbox ${state.unreadResponseCount}',
                  onPressed: () => context.push('/inbox'),
                ),
              ),
              const SizedBox(width: PtwSpacing.xs),
              Expanded(
                child: _HubAction(
                  key: const ValueKey(ComponentIds.projectDiscover),
                  icon: Icons.explore_rounded,
                  label: 'Discover',
                  onPressed: () => context.push('/discover'),
                ),
              ),
              const SizedBox(width: PtwSpacing.xs),
              Expanded(
                child: _HubAction(
                  key: const ValueKey(ComponentIds.projectAddProof),
                  icon: Icons.add_photo_alternate_rounded,
                  label: 'Proof',
                  onPressed:
                      () => context.push('/projects/${project.id}/proof/new'),
                ),
              ),
            ],
          ),
          Row(
            children: [
              TextButton.icon(
                key: const ValueKey(ComponentIds.projectCreate),
                onPressed: () => context.push('/projects/new'),
                icon: const Icon(Icons.add_rounded),
                label: const Text('New project'),
                style: TextButton.styleFrom(
                  foregroundColor: PtwColors.textOnAccent,
                  textStyle: PtwTypography.bodyStrong,
                ),
              ),
              const Spacer(),
              PopupMenuButton<String>(
                key: const ValueKey(ComponentIds.projectMenu),
                tooltip: 'Project menu',
                color: PtwColors.surfacePrimary,
                icon: const Icon(
                  Icons.more_horiz_rounded,
                  color: PtwColors.textOnAccent,
                ),
                onSelected: (value) {
                  if (value == 'reset') _reset(context, state);
                },
                itemBuilder:
                    (_) => const [
                      PopupMenuItem(
                        value: 'reset',
                        child: Text('Reset prototype'),
                      ),
                    ],
              ),
            ],
          ),
          if (proof.isNotEmpty) ...[
            const SizedBox(height: PtwSpacing.sm),
            _ProofPanel(
              projectColor: Color(project.primaryColor),
              title: proof.first.title,
              details: proof.first.details,
              time: PtwFormatters.relative(proof.first.createdAt),
              media: proof.first.media,
            ),
          ],
        ],
      ),
    );
  }
}

final class _HubAction extends StatelessWidget {
  const _HubAction({
    required this.icon,
    required this.label,
    required this.onPressed,
    super.key,
  });

  final IconData icon;
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) => OutlinedButton(
    onPressed: onPressed,
    style: OutlinedButton.styleFrom(
      minimumSize: const Size.fromHeight(62),
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
        Icon(icon, size: 20),
        const SizedBox(height: PtwSpacing.xxs),
        Text(
          label,
          maxLines: 1,
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    ),
  );
}

final class _ProofPanel extends StatelessWidget {
  const _ProofPanel({
    required this.projectColor,
    required this.title,
    required this.details,
    required this.time,
    this.media,
  });

  final Color projectColor;
  final String title;
  final String details;
  final String time;
  final PtwImageRef? media;

  @override
  Widget build(BuildContext context) => Container(
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      color: projectColor,
      border: Border.all(color: PtwColors.textOnAccent, width: 1),
      borderRadius: BorderRadius.circular(PtwRadius.xl),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (media != null)
          SizedBox(
            height: 180,
            width: double.infinity,
            child: PtwMediaImage(image: media!),
          ),
        Padding(
          padding: const EdgeInsets.all(PtwSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'PROOF · $time',
                style: PtwTypography.caption.copyWith(
                  color: PtwColors.textOnAccent,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.1,
                ),
              ),
              const SizedBox(height: PtwSpacing.sm),
              Text(
                title,
                style: PtwTypography.titleLarge.copyWith(
                  color: PtwColors.textOnAccent,
                ),
              ),
              const SizedBox(height: PtwSpacing.xs),
              Text(
                details,
                style: PtwTypography.body.copyWith(color: PtwColors.softWhite),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}
