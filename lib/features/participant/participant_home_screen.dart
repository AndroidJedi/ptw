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
import '../../ui_kit/organisms/ptw_action_sheet.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

enum _ProjectAction { share, inbox, discover, proof, create, reset }

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

  Future<void> _openActions(BuildContext context, PtwAppState state) async {
    final project = state.currentProject;
    final action = await showPtwActionSheet<_ProjectAction>(
      context,
      actions: [
        const PtwActionSheetItem(
          id: ComponentIds.projectActionShare,
          label: 'Share project',
          value: _ProjectAction.share,
        ),
        PtwActionSheetItem(
          id: ComponentIds.projectInbox,
          label:
              state.unreadResponseCount == 0
                  ? 'Inbox'
                  : 'Inbox · ${state.unreadResponseCount} unread',
          value: _ProjectAction.inbox,
        ),
        const PtwActionSheetItem(
          id: ComponentIds.projectDiscover,
          label: 'Discover',
          value: _ProjectAction.discover,
        ),
        const PtwActionSheetItem(
          id: ComponentIds.projectAddProof,
          label: 'Add proof',
          value: _ProjectAction.proof,
        ),
        const PtwActionSheetItem(
          id: ComponentIds.projectCreate,
          label: 'New project',
          value: _ProjectAction.create,
        ),
        const PtwActionSheetItem(
          id: ComponentIds.resetPrototype,
          label: 'Reset prototype',
          value: _ProjectAction.reset,
          isDestructive: true,
        ),
      ],
    );
    if (action == null || !context.mounted) return;
    switch (action) {
      case _ProjectAction.share:
        context.push('/projects/${project.id}/share');
        break;
      case _ProjectAction.inbox:
        context.push('/inbox');
        break;
      case _ProjectAction.discover:
        context.push('/discover');
        break;
      case _ProjectAction.proof:
        context.push('/projects/${project.id}/proof/new');
        break;
      case _ProjectAction.create:
        context.push('/projects/new');
        break;
      case _ProjectAction.reset:
        await _reset(context, state);
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.currentProject;
    final proof = state.evidenceFor(project.id);
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.projectHome),
      child: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PtwSpacing.screenHorizontal,
                PtwSpacing.sm,
                PtwSpacing.screenHorizontal,
                PtwSpacing.md,
              ),
              children: [
                PtwProjectTile(project: project, height: 330),
                if (proof.isNotEmpty) ...[
                  const SizedBox(height: PtwSpacing.md),
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
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.projectShare),
              label: 'Share project',
              icon: Icons.ios_share_rounded,
              onPressed: () => _openActions(context, state),
            ),
          ),
        ],
      ),
    );
  }
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
