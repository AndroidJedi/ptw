import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_gradients.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_evidence.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_response.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';
import '../../ui_kit/organisms/ptw_response_content.dart';

final class ParticipantHomeScreen extends StatefulWidget {
  const ParticipantHomeScreen({super.key});

  @override
  State<ParticipantHomeScreen> createState() => _ParticipantHomeScreenState();
}

final class _ParticipantHomeScreenState extends State<ParticipantHomeScreen> {
  final Set<String> _scheduledReadIds = {};

  void _schedulePreviewRead(PtwAppState state, List<PtwResponse> responses) {
    final ids =
        responses
            .map((response) => response.id)
            .where((id) => !_scheduledReadIds.contains(id))
            .toList();
    if (ids.isEmpty) return;
    _scheduledReadIds.addAll(ids);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      unawaited(state.markResponsesRead(ids));
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.currentProject;
    final previewProofs = state.evidenceFor(project.id).take(2).toList();
    final previewResponses = state.responsesFor(project.id).take(2).toList();
    _schedulePreviewRead(state, previewResponses);
    final heroHeight =
        (MediaQuery.sizeOf(context).height * 0.54)
            .clamp(400.0, 480.0)
            .toDouble();

    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.projectHome),
      safeArea: false,
      child: Column(
        children: [
          Expanded(
            child: ListView(
              padding: EdgeInsets.zero,
              children: [
                _ProjectHero(
                  project: project,
                  height: heroHeight,
                  onOpenFeed: () => context.push('/feed'),
                ),
                if (previewProofs.isNotEmpty) ...[
                  _ProofPreview(proofs: previewProofs),
                  const _WhiteRule(),
                ],
                _ResponsePreview(
                  responses: previewResponses,
                  unreadCount: state.unreadResponseCountFor(project.id),
                  onOpenAll: () => context.push('/inbox'),
                ),
                const SizedBox(height: PtwSpacing.md),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: PtwPinnedActionBar(
              child: PtwBlackButton(
                key: const ValueKey(ComponentIds.projectAddProof),
                label: 'Add proof',
                icon: Icons.bolt_rounded,
                onPressed:
                    () => context.push('/projects/${project.id}/proof/new'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

final class _ProjectHero extends StatelessWidget {
  const _ProjectHero({
    required this.project,
    required this.height,
    required this.onOpenFeed,
  });

  final PtwProject project;
  final double height;
  final VoidCallback onOpenFeed;

  @override
  Widget build(BuildContext context) {
    final primary = Color(project.primaryColor);
    return SizedBox(
      key: const ValueKey(ComponentIds.projectHero),
      width: double.infinity,
      height: height,
      child: Stack(
        fit: StackFit.expand,
        children: [
          PtwMediaImage(image: project.image),
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: PtwGradients.projectImageOverlay(primary),
            ),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(
              PtwSpacing.screenHorizontal,
              MediaQuery.paddingOf(context).top + PtwSpacing.sm,
              PtwSpacing.screenHorizontal,
              PtwSpacing.lg,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: _OwnerIdentity(project: project)),
                    const SizedBox(width: PtwSpacing.sm),
                    _HeroFeedButton(onTap: onOpenFeed),
                  ],
                ),
                Expanded(
                  child: PtwStickerText.project(
                    project.goal,
                    alignment: Alignment.bottomLeft,
                  ),
                ),
                const SizedBox(height: PtwSpacing.sm),
                Row(
                  children: [
                    const Icon(
                      Icons.flag_rounded,
                      color: PtwColors.textOnAccent,
                      size: 19,
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
    );
  }
}

final class _OwnerIdentity extends StatelessWidget {
  const _OwnerIdentity({required this.project});

  final PtwProject project;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        padding: const EdgeInsets.all(2),
        decoration: const BoxDecoration(
          color: PtwColors.textOnAccent,
          shape: BoxShape.circle,
        ),
        child: ClipOval(
          child: Image.asset(
            project.ownerAvatarAsset,
            width: 42,
            height: 42,
            fit: BoxFit.cover,
          ),
        ),
      ),
      const SizedBox(width: PtwSpacing.sm),
      Flexible(
        child: Text(
          '@${project.ownerHandle}',
          overflow: TextOverflow.ellipsis,
          style: PtwTypography.title.copyWith(color: PtwColors.textOnAccent),
        ),
      ),
    ],
  );
}

final class _HeroFeedButton extends StatelessWidget {
  const _HeroFeedButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    key: const ValueKey(ComponentIds.projectOpenFeed),
    color: PtwColors.ink.withValues(alpha: 0.58),
    shape: const StadiumBorder(
      side: BorderSide(color: PtwColors.textOnAccent, width: 1),
    ),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: PtwSpacing.sm,
          vertical: PtwSpacing.xs,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.explore_rounded,
              color: PtwColors.textOnAccent,
              size: 18,
            ),
            const SizedBox(width: PtwSpacing.xs),
            Text(
              'Feed',
              style: PtwTypography.label.copyWith(
                color: PtwColors.textOnAccent,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

final class _ProofPreview extends StatelessWidget {
  const _ProofPreview({required this.proofs});

  final List<PtwEvidence> proofs;

  @override
  Widget build(BuildContext context) => Column(
    key: const ValueKey(ComponentIds.projectProofsPreview),
    children: [
      for (var index = 0; index < proofs.length; index++) ...[
        _ProofUpdate(
          key: ValueKey('home_proof_${proofs[index].id}'),
          proof: proofs[index],
        ),
        if (index != proofs.length - 1) const _WhiteRule(),
      ],
    ],
  );
}

final class _ProofUpdate extends StatelessWidget {
  const _ProofUpdate({required this.proof, super.key});

  final PtwEvidence proof;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (proof.media != null)
        SizedBox(
          width: double.infinity,
          height: 180,
          child: PtwMediaImage(image: proof.media!),
        ),
      Padding(
        padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'PROOF · ${PtwFormatters.relative(proof.createdAt)}',
              style: PtwTypography.caption.copyWith(
                color: PtwColors.textOnAccent,
                fontWeight: FontWeight.w900,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: PtwSpacing.sm),
            Text(
              proof.title,
              style: PtwTypography.titleLarge.copyWith(
                color: PtwColors.textOnAccent,
              ),
            ),
            const SizedBox(height: PtwSpacing.xs),
            Text(
              proof.details,
              style: PtwTypography.body.copyWith(color: PtwColors.softWhite),
            ),
          ],
        ),
      ),
    ],
  );
}

final class _ResponsePreview extends StatelessWidget {
  const _ResponsePreview({
    required this.responses,
    required this.unreadCount,
    required this.onOpenAll,
  });

  final List<PtwResponse> responses;
  final int unreadCount;
  final VoidCallback onOpenAll;

  @override
  Widget build(BuildContext context) => Column(
    key: const ValueKey(ComponentIds.projectReactionsPreview),
    children: [
      for (var index = 0; index < responses.length; index++) ...[
        PtwResponseContent(
          key: ValueKey('home_response_${responses[index].id}'),
          response: responses[index],
          padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
        ),
        if (index != responses.length - 1) const _WhiteRule(),
      ],
      _TextAction(
        key: const ValueKey(ComponentIds.projectOpenReactions),
        label:
            unreadCount == 0
                ? 'All reactions'
                : 'All reactions · $unreadCount unread',
        onTap: onOpenAll,
      ),
    ],
  );
}

final class _TextAction extends StatelessWidget {
  const _TextAction({required this.label, required this.onTap, super.key});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: PtwColors.transparent,
    child: InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          PtwSpacing.screenHorizontal,
          PtwSpacing.sm,
          PtwSpacing.screenHorizontal,
          PtwSpacing.lg,
        ),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Text(
            label,
            style: PtwTypography.bodyStrong.copyWith(
              color: PtwColors.textOnAccent,
              decoration: TextDecoration.underline,
              decorationColor: PtwColors.textOnAccent,
              decorationThickness: 2,
            ),
          ),
        ),
      ),
    ),
  );
}

final class _WhiteRule extends StatelessWidget {
  const _WhiteRule();

  @override
  Widget build(BuildContext context) =>
      const Divider(height: 1, thickness: 1, color: PtwColors.softWhite);
}
