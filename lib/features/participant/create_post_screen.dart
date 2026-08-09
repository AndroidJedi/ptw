import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_project_draft.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';

final class CreatePostScreen extends StatefulWidget {
  const CreatePostScreen({super.key, this.intent});

  final PtwProjectDraftIntent? intent;

  @override
  State<CreatePostScreen> createState() => _CreatePostScreenState();
}

final class _CreatePostScreenState extends State<CreatePostScreen> {
  final _goalController = TextEditingController();
  final _doubtController = TextEditingController();
  final _metricStartController = TextEditingController();
  final _metricCurrentController = TextEditingController();
  final _metricTargetController = TextEditingController();
  final _metricUnitController = TextEditingController();
  final _categorySuggester = const PtwProjectCategorySuggester();
  PtwProjectDraft? _draft;
  PtwImageRef? _image;
  DateTime? _deadline;
  int _primaryColor = PtwColors.hotPink.toARGB32();
  Timer? _autosaveTimer;
  bool _initializing = false;
  bool _saving = false;
  PtwProjectCategory _category = PtwProjectCategory.other;
  bool _categoryConfirmed = false;
  bool _categoryManuallySelected = false;

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
    _doubtController.text = draft.doubt ?? '';
    final metric = draft.progressMetric;
    if (metric != null) {
      _metricStartController.text = _number(metric.start);
      _metricCurrentController.text = _number(metric.current);
      _metricTargetController.text = _number(metric.target);
      _metricUnitController.text = metric.unit;
    }
    setState(() {
      _draft = draft;
      _image = state.recoveredProjectImage ?? draft.image;
      _deadline = draft.deadline;
      _primaryColor = draft.primaryColor;
      _category = draft.category ?? _categorySuggester.suggest(draft.goal);
      _categoryConfirmed = draft.categoryConfirmed;
      _categoryManuallySelected = draft.categoryConfirmed;
      _initializing = false;
    });
  }

  @override
  void dispose() {
    _autosaveTimer?.cancel();
    _goalController.dispose();
    _doubtController.dispose();
    _metricStartController.dispose();
    _metricCurrentController.dispose();
    _metricTargetController.dispose();
    _metricUnitController.dispose();
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
    final metric = _progressMetric(strict: markPreview);
    final metricFieldsEmpty = _metricFields.every(
      (item) => item.text.trim().isEmpty,
    );
    final saved = await state.saveDraft(
      goal: _goalController.text,
      doubt: _doubtController.text,
      deadline: _deadline,
      image: _image ?? draft.image,
      primaryColor: _primaryColor,
      markPreviewGenerated: markPreview,
      category: _category,
      categoryConfirmed: _categoryConfirmed || markPreview,
      progressMetric: metric,
      clearProgressMetric: metricFieldsEmpty,
    );
    if (mounted) _draft = saved;
    return saved;
  }

  Future<void> _makeShare(PtwAppState state) async {
    final goal = _goalController.text.trim();
    final doubt = _doubtController.text.trim();
    if (goal.isEmpty ||
        goal.length > 90 ||
        doubt.length > 140 ||
        !_metricIsValid) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Add a clear challenge and complete or clear the progress metric.',
          ),
        ),
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

  List<TextEditingController> get _metricFields => [
    _metricStartController,
    _metricCurrentController,
    _metricTargetController,
    _metricUnitController,
  ];

  bool get _metricIsValid {
    final empty = _metricFields.map((item) => item.text.trim()).toList();
    if (empty.every((item) => item.isEmpty)) return true;
    return _progressMetric(strict: false) != null;
  }

  PtwProgressMetric? _progressMetric({required bool strict}) {
    final values = _metricFields.map((item) => item.text.trim()).toList();
    if (values.every((item) => item.isEmpty)) return null;
    final start = double.tryParse(values[0]);
    final current = double.tryParse(values[1]);
    final target = double.tryParse(values[2]);
    final unit = values[3];
    if (start == null ||
        current == null ||
        target == null ||
        start == target ||
        unit.isEmpty) {
      if (strict) throw const FormatException('Incomplete progress metric');
      return null;
    }
    return PtwProgressMetric(
      start: start,
      current: current,
      target: target,
      unit: unit,
    );
  }

  void _goalChanged(String value) {
    if (!_categoryManuallySelected) {
      setState(() {
        _category = _categorySuggester.suggest(value);
        _categoryConfirmed = false;
      });
    }
    _scheduleAutosave();
  }

  void _selectCategory(PtwProjectCategory value) {
    setState(() {
      _category = value;
      _categoryConfirmed = true;
      _categoryManuallySelected = true;
    });
    _scheduleAutosave();
  }

  static String _number(double value) =>
      value == value.roundToDouble()
          ? value.toInt().toString()
          : value.toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final draft = _draft;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.createProjectScreen),
      child: Column(
        children: [
          if (draft != null &&
              (draft.intent == PtwProjectDraftIntent.newChallenge ||
                  draft.hasPreview))
            Align(
              alignment: Alignment.centerLeft,
              child: PtwBackButton(
                key: const ValueKey(ComponentIds.createProjectBack),
                fallbackRoute:
                    draft.intent == PtwProjectDraftIntent.newChallenge &&
                            state.currentProjectOrNull != null
                        ? '/projects/${state.currentProject.id}'
                        : '/share/draft?source=onboarding',
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
                          onChanged: _goalChanged,
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
                        const SizedBox(height: PtwSpacing.lg),
                        Text(
                          'WHY MIGHT PEOPLE DOUBT IT? · OPTIONAL',
                          style: PtwTypography.caption.copyWith(
                            color: PtwColors.textOnAccent,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.1,
                          ),
                        ),
                        const SizedBox(height: PtwSpacing.xs),
                        TextField(
                          key: const ValueKey(ComponentIds.createProjectDoubt),
                          controller: _doubtController,
                          onChanged: (_) => _scheduleAutosave(),
                          maxLength: 140,
                          minLines: 2,
                          maxLines: 4,
                          decoration: const InputDecoration(
                            hintText: 'I have never shipped anything this big.',
                          ),
                        ),
                        const SizedBox(height: PtwSpacing.lg),
                        Text(
                          'WHAT KIND OF JOURNEY IS THIS?',
                          style: PtwTypography.caption.copyWith(
                            color: PtwColors.textOnAccent,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.1,
                          ),
                        ),
                        const SizedBox(height: PtwSpacing.xs),
                        Text(
                          _categoryConfirmed
                              ? 'Confirmed category'
                              : 'Suggested from your goal — change it if needed',
                          style: PtwTypography.body.copyWith(
                            color: PtwColors.textOnAccent.withValues(
                              alpha: 0.72,
                            ),
                          ),
                        ),
                        const SizedBox(height: PtwSpacing.sm),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final category in PtwProjectCategory.values)
                              ChoiceChip(
                                key: ValueKey(
                                  'project_category_${category.name}',
                                ),
                                label: Text(category.label),
                                selected: category == _category,
                                onSelected: (_) => _selectCategory(category),
                              ),
                          ],
                        ),
                        const SizedBox(height: PtwSpacing.lg),
                        ExpansionTile(
                          key: const ValueKey('project_progress_metric'),
                          tilePadding: EdgeInsets.zero,
                          title: Text(
                            'REAL PROGRESS METRIC · OPTIONAL',
                            style: PtwTypography.caption.copyWith(
                              color: PtwColors.textOnAccent,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 1.1,
                            ),
                          ),
                          subtitle: Text(
                            'Example: 0 → 42 → 100 users',
                            style: PtwTypography.body.copyWith(
                              color: PtwColors.textOnAccent.withValues(
                                alpha: 0.72,
                              ),
                            ),
                          ),
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: TextField(
                                    key: const ValueKey('metric_start'),
                                    controller: _metricStartController,
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                          decimal: true,
                                        ),
                                    onChanged: (_) => _scheduleAutosave(),
                                    decoration: const InputDecoration(
                                      labelText: 'Start',
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: TextField(
                                    key: const ValueKey('metric_current'),
                                    controller: _metricCurrentController,
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                          decimal: true,
                                        ),
                                    onChanged: (_) => _scheduleAutosave(),
                                    decoration: const InputDecoration(
                                      labelText: 'Current',
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: TextField(
                                    key: const ValueKey('metric_target'),
                                    controller: _metricTargetController,
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                          decimal: true,
                                        ),
                                    onChanged: (_) => _scheduleAutosave(),
                                    decoration: const InputDecoration(
                                      labelText: 'Target',
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            TextField(
                              key: const ValueKey('metric_unit'),
                              controller: _metricUnitController,
                              onChanged: (_) => _scheduleAutosave(),
                              maxLength: 18,
                              decoration: const InputDecoration(
                                labelText: 'Unit',
                                hintText: 'users, km, pages…',
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.createProjectContinue),
              label: _saving ? 'Saving draft' : 'Make my share',
              onPressed:
                  draft == null || _saving ? null : () => _makeShare(state),
            ),
          ),
        ],
      ),
    );
  }
}
