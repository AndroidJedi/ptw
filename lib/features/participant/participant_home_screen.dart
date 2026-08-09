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
import '../../models/ptw_reaction_summary.dart';
import '../../models/ptw_response.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_duck_icon.dart';
import '../../ui_kit/atoms/ptw_finish_flag_icon.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_audience_pulse.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';
import '../../ui_kit/organisms/ptw_response_content.dart';

final class ParticipantHomeScreen extends StatefulWidget {
  const ParticipantHomeScreen({
    required this.projectId,
    super.key,
    this.showActivatedMessage = false,
  });

  final String projectId;
  final bool showActivatedMessage;

  @override
  State<ParticipantHomeScreen> createState() => _ParticipantHomeScreenState();
}

final class _ParticipantHomeScreenState extends State<ParticipantHomeScreen> {
  final Set<String> _scheduledReadIds = {};

  Future<void> _editProgress(PtwAppState state, PtwProject project) async {
    final metric = project.progressMetric;
    final start = TextEditingController(
      text: metric == null ? '' : '${metric.start}',
    );
    final current = TextEditingController(
      text: metric == null ? '' : '${metric.current}',
    );
    final target = TextEditingController(
      text: metric == null ? '' : '${metric.target}',
    );
    final unit = TextEditingController(text: metric?.unit ?? '');
    String? error;
    final result = await showDialog<Object>(
      context: context,
      builder:
          (dialogContext) => StatefulBuilder(
            builder:
                (context, setDialogState) => AlertDialog(
                  title: const Text('Project progress'),
                  content: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Keep the metric factual. Share designs will use it instead '
                          'of inventing a progress claim.',
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: TextField(
                                key: const ValueKey('edit_metric_start'),
                                controller: start,
                                keyboardType:
                                    const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                decoration: const InputDecoration(
                                  labelText: 'Start',
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: TextField(
                                key: const ValueKey('edit_metric_current'),
                                controller: current,
                                keyboardType:
                                    const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                decoration: const InputDecoration(
                                  labelText: 'Current',
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: TextField(
                                key: const ValueKey('edit_metric_target'),
                                controller: target,
                                keyboardType:
                                    const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                decoration: const InputDecoration(
                                  labelText: 'Target',
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          key: const ValueKey('edit_metric_unit'),
                          controller: unit,
                          maxLength: 18,
                          decoration: const InputDecoration(
                            labelText: 'Unit',
                            hintText: 'users, km, pages…',
                          ),
                        ),
                        if (error != null)
                          Text(
                            error!,
                            style: const TextStyle(color: Color(0xFFFF5A69)),
                          ),
                      ],
                    ),
                  ),
                  actions: [
                    if (metric != null)
                      TextButton(
                        key: const ValueKey('remove_progress_metric'),
                        onPressed:
                            () => Navigator.pop(dialogContext, _removeMetric),
                        child: const Text('Remove'),
                      ),
                    TextButton(
                      onPressed: () => Navigator.pop(dialogContext),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      key: const ValueKey('save_progress_metric'),
                      onPressed: () {
                        final parsedStart = double.tryParse(start.text.trim());
                        final parsedCurrent = double.tryParse(
                          current.text.trim(),
                        );
                        final parsedTarget = double.tryParse(
                          target.text.trim(),
                        );
                        final parsedUnit = unit.text.trim();
                        if (parsedStart == null ||
                            parsedCurrent == null ||
                            parsedTarget == null ||
                            parsedStart == parsedTarget ||
                            parsedUnit.isEmpty) {
                          setDialogState(
                            () =>
                                error =
                                    'Enter start, current, target, and a unit.',
                          );
                          return;
                        }
                        Navigator.pop(
                          dialogContext,
                          PtwProgressMetric(
                            start: parsedStart,
                            current: parsedCurrent,
                            target: parsedTarget,
                            unit: parsedUnit,
                          ),
                        );
                      },
                      child: const Text('Save'),
                    ),
                  ],
                ),
          ),
    );
    start.dispose();
    current.dispose();
    target.dispose();
    unit.dispose();
    if (result is PtwProgressMetric) {
      await state.updateProjectMetadata(
        projectId: project.id,
        progressMetric: result,
      );
    } else if (identical(result, _removeMetric)) {
      await state.updateProjectMetadata(
        projectId: project.id,
        clearProgressMetric: true,
      );
    }
  }

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
    final project = state.maybeProjectById(widget.projectId);
    if (project == null) return const _MissingProjectHome();
    final previewProofs = state.evidenceFor(project.id).take(2).toList();
    final previewResponses = state.responsesFor(project.id).take(2).toList();
    final recentActivity = <_HomeActivityEntry>[
      for (final proof in previewProofs) _HomeProofActivity(proof),
      for (final response in previewResponses) _HomeResponseActivity(response),
    ]..sort(_compareHomeActivity);
    final reactionSummary = state.reactionSummaryFor(project.id);
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
                  reactionSummary: reactionSummary,
                  onOpenOthers: () => context.push('/feed'),
                  onShare:
                      () => context.push(
                        '/projects/${project.id}/share?source=project',
                      ),
                ),
                if (project.doubt?.trim().isNotEmpty == true)
                  _DoubtStatement(doubt: project.doubt!),
                _ProjectProgress(
                  metric: project.progressMetric,
                  proofCount: state.evidenceFor(project.id).length,
                  onEdit: () => unawaited(_editProgress(state, project)),
                ),
                if (recentActivity.isEmpty)
                  _EmptyProjectFrame(
                    onAddProof:
                        () => context.push('/projects/${project.id}/proof/new'),
                  )
                else ...[
                  if (widget.showActivatedMessage) const _ActivationNotice(),
                  _RecentActivity(
                    activity: recentActivity,
                    unreadCount: state.unreadResponseCountFor(project.id),
                    onOpenAll: () => context.push('/inbox'),
                  ),
                  _TextAction(
                    key: const ValueKey(ComponentIds.projectAddProof),
                    label: 'Add proof',
                    onTap:
                        () => context.push('/projects/${project.id}/proof/new'),
                  ),
                ],
                const SizedBox(height: PtwSpacing.md),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: PtwPinnedActionBar(
              child: PtwBlackButton(
                key: const ValueKey(ComponentIds.projectShareAgain),
                label: 'Share again',
                onPressed:
                    () => context.push(
                      '/projects/${project.id}/share?source=project',
                    ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

const _removeMetric = Object();

final class _ProjectProgress extends StatelessWidget {
  const _ProjectProgress({
    required this.metric,
    required this.proofCount,
    required this.onEdit,
  });

  final PtwProgressMetric? metric;
  final int proofCount;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      PtwSpacing.screenHorizontal,
      PtwSpacing.md,
      PtwSpacing.screenHorizontal,
      PtwSpacing.xs,
    ),
    child: Material(
      color: PtwColors.textOnAccent.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(18),
      child: ListTile(
        key: const ValueKey('project_progress_details'),
        leading: const Icon(Icons.trending_up_rounded),
        title: Text(
          metric == null
              ? '$proofCount ${proofCount == 1 ? 'proof' : 'proofs'} posted'
              : '${metric!.currentLabel} · ${metric!.progressLabel}',
          style: PtwTypography.bodyStrong,
        ),
        subtitle: Text(
          metric == null
              ? 'Add an optional real progress metric'
              : '${metric!.start} → ${metric!.target} ${metric!.unit}',
        ),
        trailing: const Icon(Icons.edit_outlined),
        onTap: onEdit,
      ),
    ),
  );
}

final class _ProjectHero extends StatelessWidget {
  const _ProjectHero({
    required this.project,
    required this.height,
    required this.reactionSummary,
    required this.onOpenOthers,
    required this.onShare,
  });

  final PtwProject project;
  final double height;
  final PtwReactionSummary reactionSummary;
  final VoidCallback onOpenOthers;
  final VoidCallback onShare;

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
                    _HeroShareButton(onTap: onShare),
                    const SizedBox(width: PtwSpacing.xs),
                    _HeroOthersButton(onTap: onOpenOthers),
                  ],
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      PtwSpacing.xxs,
                      PtwSpacing.zero,
                      PtwSpacing.xxs,
                      PtwSpacing.md,
                    ),
                    child: PtwStickerText.project(
                      project.goal,
                      key: const ValueKey(ComponentIds.projectHeroTitle),
                      alignment: Alignment.bottomLeft,
                    ),
                  ),
                ),
                if (reactionSummary.total > 0) ...[
                  PtwAudiencePulse(
                    key: const ValueKey(ComponentIds.projectAudiencePulse),
                    summary: reactionSummary,
                  ),
                  const SizedBox(height: PtwSpacing.sm),
                ],
                if (project.deadline != null)
                  Row(
                    children: [
                      const PtwFinishFlagIcon(size: 19),
                      const SizedBox(width: PtwSpacing.xs),
                      Text(
                        PtwFormatters.deadline(project.deadline!),
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

final class _HeroOthersButton extends StatelessWidget {
  const _HeroOthersButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: 'Others',
    excludeSemantics: true,
    child: Material(
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
              const PtwDuckIcon(
                key: ValueKey(ComponentIds.projectFeedDuck),
                size: 18,
              ),
              const SizedBox(width: PtwSpacing.xs),
              Text(
                'Others',
                style: PtwTypography.label.copyWith(
                  color: PtwColors.textOnAccent,
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

final class _HeroShareButton extends StatelessWidget {
  const _HeroShareButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: 'Share project',
    excludeSemantics: true,
    child: Material(
      key: const ValueKey(ComponentIds.participantShareButton),
      color: PtwColors.ink.withValues(alpha: 0.58),
      shape: const CircleBorder(
        side: BorderSide(color: PtwColors.textOnAccent, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: const SizedBox(
          width: 42,
          height: 42,
          child: Icon(
            Icons.ios_share_rounded,
            color: PtwColors.textOnAccent,
            size: 19,
          ),
        ),
      ),
    ),
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

final class _RecentActivity extends StatelessWidget {
  const _RecentActivity({
    required this.activity,
    required this.unreadCount,
    required this.onOpenAll,
  });

  final List<_HomeActivityEntry> activity;
  final int unreadCount;
  final VoidCallback onOpenAll;

  @override
  Widget build(BuildContext context) => Column(
    key: const ValueKey(ComponentIds.projectReactionsPreview),
    children: [
      for (var index = 0; index < activity.length; index++) ...[
        switch (activity[index]) {
          _HomeProofActivity(:final proof) => _ProofUpdate(
            key: ValueKey('home_proof_${proof.id}'),
            proof: proof,
          ),
          _HomeResponseActivity(:final response) => PtwResponseContent(
            key: ValueKey('home_response_${response.id}'),
            response: response,
            padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
          ),
        },
        const _WhiteRule(),
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

sealed class _HomeActivityEntry {
  const _HomeActivityEntry();

  DateTime get createdAt;
  String get id;
}

final class _HomeProofActivity extends _HomeActivityEntry {
  const _HomeProofActivity(this.proof);

  final PtwEvidence proof;

  @override
  DateTime get createdAt => proof.createdAt;

  @override
  String get id => proof.id;
}

final class _HomeResponseActivity extends _HomeActivityEntry {
  const _HomeResponseActivity(this.response);

  final PtwResponse response;

  @override
  DateTime get createdAt => response.createdAt;

  @override
  String get id => response.id;
}

int _compareHomeActivity(_HomeActivityEntry first, _HomeActivityEntry second) {
  final byTime = second.createdAt.compareTo(first.createdAt);
  return byTime == 0 ? first.id.compareTo(second.id) : byTime;
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

final class _DoubtStatement extends StatelessWidget {
  const _DoubtStatement({required this.doubt});

  final String doubt;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'THE DOUBT',
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.1,
          ),
        ),
        const SizedBox(height: PtwSpacing.xs),
        Text(
          doubt,
          style: PtwTypography.titleLarge.copyWith(
            color: PtwColors.textOnAccent,
          ),
        ),
      ],
    ),
  );
}

final class _EmptyProjectFrame extends StatelessWidget {
  const _EmptyProjectFrame({required this.onAddProof});

  final VoidCallback onAddProof;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      PtwSpacing.screenHorizontal,
      PtwSpacing.lg,
      PtwSpacing.screenHorizontal,
      PtwSpacing.xl,
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Your challenge is live.',
          style: PtwTypography.titleLarge.copyWith(
            color: PtwColors.textOnAccent,
          ),
        ),
        const SizedBox(height: PtwSpacing.xs),
        Text(
          'Reactions and comments will appear here.',
          style: PtwTypography.body.copyWith(color: PtwColors.softWhite),
        ),
        const SizedBox(height: PtwSpacing.md),
        _TextAction(
          key: const ValueKey(ComponentIds.projectAddProof),
          label: 'Add your first proof',
          onTap: onAddProof,
        ),
      ],
    ),
  );
}

final class _ActivationNotice extends StatelessWidget {
  const _ActivationNotice();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
    child: Text(
      'Your challenge is live.',
      style: PtwTypography.title.copyWith(color: PtwColors.textOnAccent),
    ),
  );
}

final class _MissingProjectHome extends StatelessWidget {
  const _MissingProjectHome();

  @override
  Widget build(BuildContext context) => const PtwImmersivePage(
    child: Center(
      child: PtwStickerText.hero(
        'Project unavailable',
        textAlign: TextAlign.center,
      ),
    ),
  );
}
