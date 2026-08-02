import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_response.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_creator_shell.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class ParticipantHomeScreen extends StatelessWidget {
  const ParticipantHomeScreen({super.key});

  Future<void> _reset(BuildContext context, PtwAppState state) async {
    final approved = await showDialog<bool>(
      context: context,
      builder:
          (context) => AlertDialog(
            title: const Text('Reset prototype?'),
            content: const Text(
              'Local projects and responses will be replaced by seed data.',
            ),
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
    final responses = state.creatorResponses.take(2).toList();
    return PtwCreatorShell(
      destination: PtwCreatorDestination.project,
      child: SafeArea(
        child: ListView(
          key: const ValueKey(ComponentIds.projectHome),
          padding: const EdgeInsets.fromLTRB(
            PtwSpacing.screenHorizontal,
            PtwSpacing.sm,
            PtwSpacing.screenHorizontal,
            124,
          ),
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'PROVE THEM WRONG',
                        style: PtwTypography.caption.copyWith(
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1.1,
                        ),
                      ),
                      Text('Your project', style: PtwTypography.titleLarge),
                    ],
                  ),
                ),
                IconButton.filled(
                  tooltip: 'Create another project',
                  onPressed: () => context.push('/projects/new'),
                  style: IconButton.styleFrom(backgroundColor: PtwColors.ink),
                  icon: const Icon(
                    Icons.add_rounded,
                    color: PtwColors.textOnAccent,
                  ),
                ),
                IconButton(
                  key: const ValueKey(ComponentIds.resetPrototype),
                  tooltip: 'Reset prototype data',
                  onPressed: () => _reset(context, state),
                  icon: const Icon(Icons.restart_alt_rounded),
                ),
              ],
            ),
            const SizedBox(height: PtwSpacing.md),
            PtwProjectTile(project: project, height: 330),
            const SizedBox(height: PtwSpacing.md),
            PtwBlackButton(
              key: const ValueKey(ComponentIds.projectShare),
              label: 'Share project',
              icon: Icons.ios_share_rounded,
              onPressed: () => context.push('/projects/${project.id}/share'),
            ),
            const SizedBox(height: PtwSpacing.sm),
            OutlinedButton.icon(
              key: const ValueKey(ComponentIds.projectAddProof),
              onPressed:
                  () => context.push('/projects/${project.id}/proof/new'),
              icon: const Icon(Icons.add_photo_alternate_rounded),
              label: const Text('Add proof'),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(54),
                foregroundColor: PtwColors.ink,
                side: const BorderSide(color: PtwColors.ink, width: 2),
                textStyle: PtwTypography.button,
                shape: const StadiumBorder(),
              ),
            ),
            const SizedBox(height: PtwSpacing.xl),
            _SectionHeader(
              title: 'Latest proof',
              action:
                  proof.isEmpty
                      ? null
                      : PtwFormatters.relative(proof.first.createdAt),
            ),
            const SizedBox(height: PtwSpacing.xs),
            if (proof.isEmpty)
              const _EmptyCard(
                text: 'Nothing polished. Just show the next real step.',
              )
            else
              Container(
                padding: const EdgeInsets.all(PtwSpacing.md),
                decoration: BoxDecoration(
                  color: PtwColors.surfacePrimary,
                  borderRadius: BorderRadius.circular(PtwRadius.lg),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: Color(project.primaryColor),
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.bolt_rounded,
                        color: PtwColors.textOnAccent,
                      ),
                    ),
                    const SizedBox(width: PtwSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            proof.first.title,
                            style: PtwTypography.bodyStrong,
                          ),
                          Text(
                            proof.first.details,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: PtwTypography.caption,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: PtwSpacing.xl),
            _SectionHeader(
              title: 'Anonymous inbox',
              action: responses.isEmpty ? null : 'See all',
              onTap: responses.isEmpty ? null : () => context.go('/inbox'),
            ),
            const SizedBox(height: PtwSpacing.xs),
            if (responses.isEmpty)
              const _EmptyCard(
                text: 'Share your link. The honest takes land here.',
              )
            else
              Container(
                key: const ValueKey(ComponentIds.projectInboxPreview),
                decoration: BoxDecoration(
                  color: PtwColors.surfacePrimary,
                  borderRadius: BorderRadius.circular(PtwRadius.lg),
                ),
                child: Column(
                  children: [
                    for (var index = 0; index < responses.length; index++) ...[
                      _ResponsePreview(response: responses[index]),
                      if (index != responses.length - 1)
                        const Divider(height: 1, indent: 16, endIndent: 16),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

final class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.action, this.onTap});

  final String title;
  final String? action;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(child: Text(title, style: PtwTypography.title)),
      if (action != null) TextButton(onPressed: onTap, child: Text(action!)),
    ],
  );
}

final class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(PtwSpacing.lg),
    decoration: BoxDecoration(
      color: PtwColors.surfacePrimary,
      borderRadius: BorderRadius.circular(PtwRadius.lg),
    ),
    child: Text(text, style: PtwTypography.bodyStrong),
  );
}

final class _ResponsePreview extends StatelessWidget {
  const _ResponsePreview({required this.response});
  final PtwResponse response;

  @override
  Widget build(BuildContext context) => ListTile(
    onTap: () => context.go('/inbox'),
    leading: CircleAvatar(
      backgroundColor:
          response.side == PtwResponseSide.believe
              ? PtwColors.electricBlue
              : PtwColors.hotPink,
      child: Icon(
        response.side == PtwResponseSide.believe
            ? Icons.thumb_up_rounded
            : Icons.thumb_down_rounded,
        color: PtwColors.textOnAccent,
        size: 18,
      ),
    ),
    title: Text(
      response.message,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: PtwTypography.bodyStrong,
    ),
    subtitle: Text('Anonymous · ${PtwFormatters.relative(response.createdAt)}'),
    trailing:
        response.isRead
            ? const Icon(Icons.chevron_right_rounded)
            : const Icon(Icons.circle, color: PtwColors.hotPink, size: 10),
  );
}
