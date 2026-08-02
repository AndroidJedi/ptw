import 'dart:async';

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
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';

final class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key});

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

final class _InboxScreenState extends State<InboxScreen> {
  bool _scheduledReadCommit = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_scheduledReadCommit) return;
    _scheduledReadCommit = true;
    final state = PtwScope.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      unawaited(state.markCreatorResponsesRead());
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final responses = state.creatorResponses;
    const background = PtwColors.hotPink;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.inboxScreen),
      backgroundColor: background,
      child: Column(
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: PtwBackButton(
              key: ValueKey(ComponentIds.inboxBack),
              fallbackRoute: '/',
            ),
          ),
          Expanded(
            child:
                responses.isEmpty
                    ? Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: PtwSpacing.screenHorizontal,
                      ),
                      child: Center(
                        child: PtwBlackButton(
                          label: 'Share project',
                          icon: Icons.ios_share_rounded,
                          onPressed:
                              () => context.push(
                                '/projects/${state.currentProject.id}/share',
                              ),
                        ),
                      ),
                    )
                    : ListView.separated(
                      key: const ValueKey(ComponentIds.inboxList),
                      padding: const EdgeInsets.fromLTRB(
                        PtwSpacing.screenHorizontal,
                        PtwSpacing.xs,
                        PtwSpacing.screenHorizontal,
                        PtwSpacing.xxl,
                      ),
                      itemCount: responses.length,
                      separatorBuilder:
                          (_, __) => const SizedBox(height: PtwSpacing.sm),
                      itemBuilder: (context, index) {
                        final response = responses[index];
                        return _ResponsePanel(
                          key: ValueKey('response_${response.id}'),
                          response: response,
                          color: background,
                        );
                      },
                    ),
          ),
        ],
      ),
    );
  }
}

final class _ResponsePanel extends StatelessWidget {
  const _ResponsePanel({
    required this.response,
    required this.color,
    super.key,
  });

  final PtwResponse response;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(PtwSpacing.lg),
    decoration: BoxDecoration(
      color: color,
      border: Border.all(color: PtwColors.textOnAccent, width: 1),
      borderRadius: BorderRadius.circular(PtwRadius.xl),
    ),
    child: Column(
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
          style: PtwTypography.bodyStrong.copyWith(color: PtwColors.softWhite),
        ),
      ],
    ),
  );
}
