import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_project_draft.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';

/// The deliberately small challenge entry used after activation.
///
/// Category and journey metadata are inferred after the user supplies the one
/// required input: the goal that becomes the Story headline.
final class CreatePostScreen extends StatefulWidget {
  const CreatePostScreen({super.key, this.intent});

  final PtwProjectDraftIntent? intent;

  @override
  State<CreatePostScreen> createState() => _CreatePostScreenState();
}

final class _CreatePostScreenState extends State<CreatePostScreen> {
  final _goalController = TextEditingController();
  final _categorySuggester = const PtwProjectCategorySuggester();
  PtwProjectDraft? _draft;
  Timer? _autosaveTimer;
  bool _initializing = false;
  bool _saving = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_draft == null && !_initializing) {
      _initializing = true;
      unawaited(_initialize(PtwScope.of(context)));
    }
  }

  Future<void> _initialize(PtwAppState state) async {
    final intent =
        widget.intent ??
        (state.isActivated
            ? PtwProjectDraftIntent.newChallenge
            : PtwProjectDraftIntent.firstProject);
    final draft = await state.ensureDraft(intent);
    if (!mounted) return;
    _goalController.text = draft.goal;
    setState(() {
      _draft = draft;
      _initializing = false;
    });
  }

  @override
  void dispose() {
    _autosaveTimer?.cancel();
    _goalController.dispose();
    super.dispose();
  }

  void _scheduleAutosave() {
    _autosaveTimer?.cancel();
    _autosaveTimer = Timer(const Duration(milliseconds: 300), () {
      if (!mounted || _draft == null) return;
      unawaited(_save(PtwScope.of(context), markPreview: false));
    });
  }

  Future<PtwProjectDraft?> _save(
    PtwAppState state, {
    required bool markPreview,
  }) async {
    final draft = _draft;
    if (draft == null) return null;
    final goal = _goalController.text.trim();
    final saved = await state.saveDraft(
      goal: goal,
      doubt: draft.doubt ?? '',
      deadline: draft.deadline,
      image: draft.image,
      primaryColor: draft.primaryColor,
      markPreviewGenerated: markPreview,
      category: _categorySuggester.suggest(goal),
      categoryConfirmed: false,
      progressMetric: draft.progressMetric,
    );
    if (mounted) _draft = saved;
    return saved;
  }

  Future<void> _makeShare(PtwAppState state) async {
    final goal = _goalController.text.trim();
    if (goal.isEmpty || goal.length > 90) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add a clear challenge first.')),
      );
      return;
    }
    _autosaveTimer?.cancel();
    setState(() => _saving = true);
    try {
      final saved = await _save(state, markPreview: true);
      if (!mounted || saved == null) return;
      final source =
          saved.intent == PtwProjectDraftIntent.firstProject
              ? 'onboarding'
              : 'newChallenge';
      context.go('/share/draft?source=$source');
    } on Object {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Your draft could not be saved.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final draft = _draft;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.createProjectScreen),
      child: Column(
        children: [
          if (draft?.intent == PtwProjectDraftIntent.newChallenge)
            Align(
              alignment: Alignment.centerLeft,
              child: PtwBackButton(
                key: const ValueKey(ComponentIds.createProjectBack),
                fallbackRoute:
                    state.currentProjectOrNull == null
                        ? '/'
                        : '/projects/${state.currentProject.id}',
              ),
            ),
          Expanded(
            child:
                draft == null
                    ? const Center(
                      child: CircularProgressIndicator(
                        color: PtwColors.textOnAccent,
                      ),
                    )
                    : ListView(
                      padding: const EdgeInsets.all(
                        PtwSpacing.screenHorizontal,
                      ),
                      children: [
                        const PtwStickerText.hero('What will you prove?'),
                        const SizedBox(height: PtwSpacing.xl),
                        TextField(
                          key: const ValueKey(ComponentIds.createProjectGoal),
                          controller: _goalController,
                          onChanged: (_) => _scheduleAutosave(),
                          maxLength: 90,
                          minLines: 3,
                          maxLines: 4,
                          autofocus: draft.goal.isEmpty,
                          style: PtwTypography.title,
                          decoration: const InputDecoration(
                            hintText:
                                'Launch my product and reach 100 active users',
                            alignLabelWithHint: true,
                          ),
                        ),
                      ],
                    ),
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.createProjectContinue),
              label: _saving ? 'Generating Story' : 'Make my share',
              onPressed:
                  draft == null || _saving ? null : () => _makeShare(state),
            ),
          ),
        ],
      ),
    );
  }
}
