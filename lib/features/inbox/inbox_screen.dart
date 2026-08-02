import 'package:flutter/material.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_response.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/organisms/ptw_creator_shell.dart';

final class InboxScreen extends StatelessWidget {
  const InboxScreen({super.key});

  Future<void> _open(
    BuildContext context,
    PtwAppState state,
    PtwResponse response,
  ) async {
    await state.markResponseRead(response.id);
    if (!context.mounted) return;
    final project = state.projectById(response.projectId);
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: PtwColors.transparent,
      builder:
          (context) => Container(
            margin: const EdgeInsets.all(PtwSpacing.sm),
            padding: const EdgeInsets.all(PtwSpacing.lg),
            decoration: BoxDecoration(
              color: Color(project.primaryColor),
              borderRadius: BorderRadius.circular(PtwRadius.xl),
            ),
            child: SafeArea(
              top: false,
              child: Column(
                mainAxisSize: MainAxisSize.min,
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
            ),
          ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final responses = state.creatorResponses;
    return PtwCreatorShell(
      destination: PtwCreatorDestination.inbox,
      child: SafeArea(
        child: Padding(
          key: const ValueKey(ComponentIds.inboxScreen),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 110),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Anonymous inbox', style: PtwTypography.display),
              const SizedBox(height: PtwSpacing.xs),
              Text(
                '${state.unreadResponseCount} unread · only you can see these',
                style: PtwTypography.body.copyWith(
                  color: PtwColors.textSecondary,
                ),
              ),
              const SizedBox(height: PtwSpacing.lg),
              Expanded(
                child:
                    responses.isEmpty
                        ? const Center(
                          child: Text('Share a project to get honest takes.'),
                        )
                        : ListView.separated(
                          key: const ValueKey(ComponentIds.inboxList),
                          itemCount: responses.length,
                          separatorBuilder:
                              (_, __) => const SizedBox(height: PtwSpacing.sm),
                          itemBuilder: (context, index) {
                            final response = responses[index];
                            final project = state.projectById(
                              response.projectId,
                            );
                            return Material(
                              color: PtwColors.surfacePrimary,
                              borderRadius: BorderRadius.circular(PtwRadius.lg),
                              child: InkWell(
                                key: ValueKey('response_${response.id}'),
                                onTap: () => _open(context, state, response),
                                borderRadius: BorderRadius.circular(
                                  PtwRadius.lg,
                                ),
                                child: Padding(
                                  padding: const EdgeInsets.all(PtwSpacing.sm),
                                  child: Row(
                                    children: [
                                      ClipRRect(
                                        borderRadius: BorderRadius.circular(
                                          PtwRadius.md,
                                        ),
                                        child: SizedBox(
                                          width: 66,
                                          height: 76,
                                          child: PtwMediaImage(
                                            image: project.image,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: PtwSpacing.sm),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Container(
                                                  padding:
                                                      const EdgeInsets.symmetric(
                                                        horizontal: 8,
                                                        vertical: 4,
                                                      ),
                                                  decoration: BoxDecoration(
                                                    color:
                                                        response.side ==
                                                                PtwResponseSide
                                                                    .believe
                                                            ? PtwColors
                                                                .electricBlue
                                                            : PtwColors.hotPink,
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                          PtwRadius.pill,
                                                        ),
                                                  ),
                                                  child: Text(
                                                    response.side ==
                                                            PtwResponseSide
                                                                .believe
                                                        ? 'BELIEVE'
                                                        : 'DOUBT',
                                                    style: PtwTypography.caption
                                                        .copyWith(
                                                          color:
                                                              PtwColors
                                                                  .textOnAccent,
                                                          fontSize: 9,
                                                          fontWeight:
                                                              FontWeight.w900,
                                                        ),
                                                  ),
                                                ),
                                                const Spacer(),
                                                if (!response.isRead)
                                                  const Icon(
                                                    Icons.circle,
                                                    color: PtwColors.hotPink,
                                                    size: 9,
                                                  ),
                                              ],
                                            ),
                                            const SizedBox(height: 6),
                                            Text(
                                              response.message,
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: PtwTypography.bodyStrong,
                                            ),
                                            const SizedBox(height: 4),
                                            Text(
                                              'Anonymous · ${PtwFormatters.relative(response.createdAt)}',
                                              style: PtwTypography.caption,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
