import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';
import '../../ui_kit/organisms/ptw_response_content.dart';

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
    final responseIds =
        state
            .responsesFor(state.currentProject.id)
            .map((response) => response.id)
            .toList();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      unawaited(state.markResponsesRead(responseIds));
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final responses = state.responsesFor(state.currentProject.id);
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
                    ? const SizedBox.shrink()
                    : ListView.separated(
                      key: const ValueKey(ComponentIds.inboxList),
                      padding: const EdgeInsets.fromLTRB(
                        PtwSpacing.screenHorizontal,
                        PtwSpacing.xs,
                        PtwSpacing.screenHorizontal,
                        PtwSpacing.md,
                      ),
                      itemCount: responses.length,
                      separatorBuilder:
                          (_, __) => const SizedBox(height: PtwSpacing.sm),
                      itemBuilder: (context, index) {
                        final response = responses[index];
                        return PtwResponseContent(
                          key: ValueKey('response_${response.id}'),
                          response: response,
                          framed: true,
                        );
                      },
                    ),
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.inboxShare),
              label: 'Share project',
              onPressed:
                  () => context.push(
                    '/projects/${state.currentProject.id}/share?event=newSkeptic&template=criticism',
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
