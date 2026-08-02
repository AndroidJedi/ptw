import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_gradients.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_response.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class SharedPromiseScreen extends StatelessWidget {
  const SharedPromiseScreen({required this.handle, super.key});

  final String handle;

  @override
  Widget build(BuildContext context) {
    final project = PtwScope.of(context).projectForHandle(handle);
    return project == null
        ? const _ProjectNotFound()
        : GuestStoryScreen(projectId: project.id);
  }
}

final class GuestStoryScreen extends StatefulWidget {
  const GuestStoryScreen({required this.projectId, super.key});

  final String projectId;

  @override
  State<GuestStoryScreen> createState() => _GuestStoryScreenState();
}

final class _GuestStoryScreenState extends State<GuestStoryScreen> {
  final _messageController = TextEditingController();
  PtwResponseSide? _side;
  bool _sending = false;

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  bool get _canSend =>
      !_sending && _side != null && _messageController.text.trim().isNotEmpty;

  Future<void> _send(PtwAppState state) async {
    if (!_canSend) return;
    setState(() => _sending = true);
    try {
      await state.submitResponse(
        projectId: widget.projectId,
        side: _side!,
        message: _messageController.text,
      );
      if (mounted) context.go('/p/${widget.projectId}/sent');
    } on Exception {
      if (!mounted) return;
      setState(() => _sending = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not send. Try once more.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(widget.projectId);
    if (project == null) return const _ProjectNotFound();
    final primary = Color(project.primaryColor);
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.visitorComposer),
      backgroundColor: primary,
      decoration: BoxDecoration(gradient: PtwGradients.project(primary)),
      child: LayoutBuilder(
        builder:
            (context, constraints) => SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - 32,
                ),
                child: Column(
                  children: [
                    if (context.canPop())
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: PtwBackButton(
                          key: ValueKey(ComponentIds.visitorBack),
                          fallbackRoute: '/discover',
                        ),
                      ),
                    PtwProjectTile(
                      project: project,
                      height: 244,
                      compact: true,
                    ),
                    const SizedBox(height: PtwSpacing.sm),
                    Row(
                      children: [
                        Expanded(
                          child: _PositionButton(
                            key: const ValueKey(ComponentIds.responseBelieve),
                            label: 'Believe',
                            icon: Icons.thumb_up_rounded,
                            selected: _side == PtwResponseSide.believe,
                            onTap:
                                () => setState(
                                  () => _side = PtwResponseSide.believe,
                                ),
                          ),
                        ),
                        const SizedBox(width: PtwSpacing.xs),
                        Expanded(
                          child: _PositionButton(
                            key: const ValueKey(ComponentIds.responseDoubt),
                            label: 'Doubt',
                            icon: Icons.thumb_down_rounded,
                            selected: _side == PtwResponseSide.doubt,
                            onTap:
                                () => setState(
                                  () => _side = PtwResponseSide.doubt,
                                ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: PtwSpacing.sm),
                    TextField(
                      key: const ValueKey(ComponentIds.responseMessage),
                      controller: _messageController,
                      maxLength: 180,
                      minLines: 3,
                      maxLines: 3,
                      onChanged: (_) => setState(() {}),
                      style: PtwTypography.bodyStrong,
                      decoration: InputDecoration(
                        hintText: 'Say what you really think…',
                        counterText: '',
                        fillColor: PtwColors.softWhite,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(PtwRadius.lg),
                          borderSide: BorderSide.none,
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(PtwRadius.lg),
                          borderSide: BorderSide.none,
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(PtwRadius.lg),
                          borderSide: const BorderSide(
                            color: PtwColors.ink,
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: PtwSpacing.sm),
                    Text(
                      '${state.responseCountFor(project.id)} people responded',
                      textAlign: TextAlign.center,
                      style: PtwTypography.bodyStrong.copyWith(
                        color: PtwColors.textOnAccent,
                      ),
                    ),
                    const SizedBox(height: PtwSpacing.md),
                    PtwBlackButton(
                      key: const ValueKey(ComponentIds.responseSend),
                      label: 'Send anonymously',
                      icon: Icons.arrow_upward_rounded,
                      onPressed: _canSend ? () => _send(state) : null,
                    ),
                  ],
                ),
              ),
            ),
      ),
    );
  }
}

final class _PositionButton extends StatelessWidget {
  const _PositionButton({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: selected ? PtwColors.ink : PtwColors.softWhite,
    shape: const StadiumBorder(
      side: BorderSide(color: PtwColors.textOnAccent, width: 1),
    ),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(PtwRadius.pill),
      child: SizedBox(
        height: 50,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              color: selected ? PtwColors.textOnAccent : PtwColors.ink,
            ),
            const SizedBox(width: PtwSpacing.xs),
            Text(
              label,
              style: PtwTypography.button.copyWith(
                color: selected ? PtwColors.textOnAccent : PtwColors.ink,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

final class _ProjectNotFound extends StatelessWidget {
  const _ProjectNotFound();

  @override
  Widget build(BuildContext context) => PtwImmersivePage(
    child: Padding(
      padding: const EdgeInsets.all(PtwSpacing.lg),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'Project unavailable',
            style: PtwTypography.titleLarge.copyWith(
              color: PtwColors.textOnAccent,
            ),
          ),
          const SizedBox(height: PtwSpacing.lg),
          PtwBlackButton(
            label: 'Discover projects',
            onPressed: () => context.go('/discover'),
          ),
        ],
      ),
    ),
  );
}

final class ResponseSentScreen extends StatelessWidget {
  const ResponseSentScreen({required this.projectId, super.key});

  final String projectId;

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(projectId);
    if (project == null) return const _ProjectNotFound();
    final primary = Color(project.primaryColor);
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.responseSent),
      backgroundColor: primary,
      decoration: BoxDecoration(gradient: PtwGradients.project(primary)),
      child: Padding(
        padding: const EdgeInsets.all(PtwSpacing.lg),
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: PtwBackButton(
                key: const ValueKey(ComponentIds.responseSentBack),
                fallbackRoute: '/p/$projectId',
              ),
            ),
            const Spacer(flex: 2),
            Container(
              width: 112,
              height: 112,
              decoration: const BoxDecoration(
                color: PtwColors.surfacePrimary,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.check_rounded, size: 72, color: primary),
            ),
            const SizedBox(height: PtwSpacing.lg),
            Text(
              'Sent!',
              style: PtwTypography.display.copyWith(
                color: PtwColors.textOnAccent,
                fontSize: 46,
              ),
            ),
            const SizedBox(height: PtwSpacing.xs),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(
                  Icons.arrow_downward_rounded,
                  color: PtwColors.textOnAccent,
                ),
                const SizedBox(width: PtwSpacing.xs),
                Flexible(
                  child: Text(
                    '${state.responseCountFor(project.id)} people have responded',
                    textAlign: TextAlign.center,
                    style: PtwTypography.title.copyWith(
                      color: PtwColors.textOnAccent,
                    ),
                  ),
                ),
                const SizedBox(width: PtwSpacing.xs),
                const Icon(
                  Icons.arrow_downward_rounded,
                  color: PtwColors.textOnAccent,
                ),
              ],
            ),
            const Spacer(flex: 3),
            PtwBlackButton(
              key: const ValueKey(ComponentIds.responseStartProject),
              label: 'Start your own project',
              icon: Icons.bolt_rounded,
              onPressed: () => context.go('/projects/new?source=response'),
            ),
            TextButton(
              key: const ValueKey(ComponentIds.responseSendAnother),
              onPressed: () => context.go('/p/$projectId'),
              child: Text(
                'Send another',
                style: PtwTypography.bodyStrong.copyWith(
                  color: PtwColors.textOnAccent,
                  decoration: TextDecoration.underline,
                  decorationColor: PtwColors.textOnAccent,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
