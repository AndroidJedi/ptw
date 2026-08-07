import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../models/ptw_story_composition.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import 'ptw_story_card.dart';
import 'ptw_story_constructor_controller.dart';
import 'story_look_presets.dart';
import 'studio_models.dart';

enum _StoryBuilderTool { text, looks, stickers }

final class PtwStoryBuilder extends StatefulWidget {
  const PtwStoryBuilder({
    required this.controller,
    required this.onClose,
    required this.onContinue,
    super.key,
  });

  final PtwStoryConstructorController controller;
  final VoidCallback onClose;
  final VoidCallback onContinue;

  @override
  State<PtwStoryBuilder> createState() => _PtwStoryBuilderState();
}

final class _PtwStoryBuilderState extends State<PtwStoryBuilder> {
  late final TextEditingController _headline;
  late final TextEditingController _dare;
  final _headlineFocus = FocusNode(debugLabel: 'Story headline');
  final _dareFocus = FocusNode(debugLabel: 'Story dare');
  var _tool = _StoryBuilderTool.stickers;
  var _category = MemeStickerCategory.hype;
  PtwStoryTextTarget? _selectedText;
  bool _headlineInvalid = false;
  bool _dareInvalid = false;

  @override
  void initState() {
    super.initState();
    _headline = TextEditingController(
      text: widget.controller.composition.headline,
    );
    _dare = TextEditingController(text: widget.controller.composition.dare);
  }

  @override
  void didUpdateWidget(PtwStoryBuilder oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) _syncTextFromComposition();
  }

  @override
  void dispose() {
    _headline.dispose();
    _dare.dispose();
    _headlineFocus.dispose();
    _dareFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) {
      final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
      return Column(
        children: [
          _BuilderTopBar(
            hasChanges: widget.controller.hasChanges,
            onClose: widget.onClose,
            onReset: _reset,
            onMagic: () {
              _clearTextSelection();
              widget.controller.cycleLook();
            },
          ),
          Expanded(
            child: _BuilderCanvas(
              controller: widget.controller,
              selectedText: _selectedText,
              onTextSelected: _selectText,
              onCanvasTap: _clearTextSelection,
              onStickerSelected: () {
                _unfocusText();
                if (mounted) {
                  setState(() {
                    _tool = _StoryBuilderTool.stickers;
                    _selectedText = null;
                  });
                }
              },
            ),
          ),
          _ToolSelector(selected: _tool, onSelected: _selectTool),
          SizedBox(
            height: keyboardOpen ? 138 : 154,
            child: DecoratedBox(
              decoration: const BoxDecoration(
                color: Color(0xFF171F36),
                border: Border(top: BorderSide(color: Color(0xFF2B3552))),
              ),
              child: switch (_tool) {
                _StoryBuilderTool.text => _TextTool(
                  headline: _headline,
                  dare: _dare,
                  headlineFocus: _headlineFocus,
                  dareFocus: _dareFocus,
                  selectedText: _selectedText,
                  headlineInvalid: _headlineInvalid,
                  dareInvalid: _dareInvalid,
                  onHeadlineTap: () => _selectText(PtwStoryTextTarget.headline),
                  onDareTap: () => _selectText(PtwStoryTextTarget.dare),
                  onChanged: _updateText,
                  onDone: _unfocusText,
                ),
                _StoryBuilderTool.looks => _LooksTool(
                  controller: widget.controller,
                  onApply: _clearTextSelection,
                ),
                _StoryBuilderTool.stickers => _StickersTool(
                  controller: widget.controller,
                  category: _category,
                  onCategoryChanged:
                      (category) => setState(() => _category = category),
                  onAdd: _addSticker,
                ),
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
            child: SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton.icon(
                key: const ValueKey(ComponentIds.storyContinue),
                onPressed: _continue,
                style: FilledButton.styleFrom(
                  backgroundColor: PtwColors.hotPink,
                  foregroundColor: PtwColors.textOnAccent,
                  shape: const StadiumBorder(),
                ),
                icon: const Icon(Icons.arrow_forward_rounded),
                label: const Text(
                  'Continue',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                ),
              ),
            ),
          ),
        ],
      );
    },
  );

  void _selectTool(_StoryBuilderTool tool) {
    if (tool == _StoryBuilderTool.text) {
      _selectText(_selectedText ?? PtwStoryTextTarget.headline);
      return;
    }
    _unfocusText();
    setState(() {
      _tool = tool;
      _selectedText = null;
    });
  }

  void _selectText(PtwStoryTextTarget target) {
    widget.controller.selectSticker(null);
    setState(() {
      _tool = _StoryBuilderTool.text;
      _selectedText = target;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final focus =
          target == PtwStoryTextTarget.headline ? _headlineFocus : _dareFocus;
      focus.requestFocus();
    });
  }

  void _clearTextSelection() {
    _unfocusText();
    if (_selectedText != null && mounted) {
      setState(() => _selectedText = null);
    }
  }

  void _unfocusText() {
    _headlineFocus.unfocus();
    _dareFocus.unfocus();
  }

  void _updateText() {
    if (_headlineInvalid || _dareInvalid) {
      setState(() {
        _headlineInvalid = false;
        _dareInvalid = false;
      });
    }
    widget.controller.updateText(headline: _headline.text, dare: _dare.text);
  }

  void _addSticker(String stickerId) {
    _unfocusText();
    setState(() {
      _tool = _StoryBuilderTool.stickers;
      _selectedText = null;
    });
    widget.controller.addSticker(stickerId);
  }

  void _reset() {
    _unfocusText();
    widget.controller.reset();
    _syncTextFromComposition();
    setState(() {
      _tool = _StoryBuilderTool.stickers;
      _selectedText = null;
      _headlineInvalid = false;
      _dareInvalid = false;
    });
  }

  void _syncTextFromComposition() {
    final composition = widget.controller.composition;
    _headline.value = TextEditingValue(
      text: composition.headline,
      selection: TextSelection.collapsed(offset: composition.headline.length),
    );
    _dare.value = TextEditingValue(
      text: composition.dare,
      selection: TextSelection.collapsed(offset: composition.dare.length),
    );
  }

  void _continue() {
    final headline = _headline.text.trim();
    final dare = _dare.text.trim();
    final headlineInvalid = headline.isEmpty;
    final dareInvalid = dare.isEmpty;
    if (headlineInvalid || dareInvalid) {
      setState(() {
        _tool = _StoryBuilderTool.text;
        _headlineInvalid = headlineInvalid;
        _dareInvalid = dareInvalid;
        _selectedText =
            headlineInvalid
                ? PtwStoryTextTarget.headline
                : PtwStoryTextTarget.dare;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        (headlineInvalid ? _headlineFocus : _dareFocus).requestFocus();
      });
      return;
    }
    _headline.text = headline;
    _dare.text = dare;
    widget.controller.updateText(headline: headline, dare: dare);
    _unfocusText();
    widget.controller.selectSticker(null);
    widget.onContinue();
  }
}

final class _BuilderTopBar extends StatelessWidget {
  const _BuilderTopBar({
    required this.hasChanges,
    required this.onClose,
    required this.onReset,
    required this.onMagic,
  });

  final bool hasChanges;
  final VoidCallback onClose;
  final VoidCallback onReset;
  final VoidCallback onMagic;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 52,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 7),
      child: Row(
        children: [
          IconButton(
            key: const ValueKey(ComponentIds.shareBack),
            tooltip: 'Close builder',
            onPressed: onClose,
            color: PtwColors.textOnAccent,
            icon: const Icon(Icons.close_rounded, size: 28),
          ),
          const Expanded(
            child: Text(
              'BUILD YOUR STORY',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PtwColors.textOnAccent,
                fontFamily: 'PtwLilitaOne',
                fontSize: 20,
                letterSpacing: 0.6,
              ),
            ),
          ),
          if (hasChanges)
            IconButton(
              key: const ValueKey(ComponentIds.storyReset),
              tooltip: 'Reset Story',
              onPressed: onReset,
              color: PtwColors.textOnAccent,
              icon: const Icon(Icons.restart_alt_rounded),
            )
          else
            const SizedBox(width: 48),
          IconButton.filled(
            key: const ValueKey(ComponentIds.shareGenerateAnother),
            tooltip: 'Magic look',
            onPressed: onMagic,
            style: IconButton.styleFrom(
              backgroundColor: PtwColors.accentYellow,
              foregroundColor: PtwColors.ink,
            ),
            icon: const Icon(Icons.auto_awesome_rounded),
          ),
        ],
      ),
    ),
  );
}

final class _BuilderCanvas extends StatelessWidget {
  const _BuilderCanvas({
    required this.controller,
    required this.selectedText,
    required this.onTextSelected,
    required this.onCanvasTap,
    required this.onStickerSelected,
  });

  final PtwStoryConstructorController controller;
  final PtwStoryTextTarget? selectedText;
  final ValueChanged<PtwStoryTextTarget> onTextSelected;
  final VoidCallback onCanvasTap;
  final VoidCallback onStickerSelected;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(14, 4, 14, 8),
    child: LayoutBuilder(
      builder: (context, constraints) {
        final availableWidth = math.max(1.0, constraints.maxWidth);
        final availableHeight = math.max(1.0, constraints.maxHeight);
        final width = math.min(availableWidth, availableHeight * 9 / 16);
        final height = width * 16 / 9;
        return Center(
          child: Container(
            key: const ValueKey(ComponentIds.storyBuilderCanvas),
            width: width,
            height: height,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
              border: Border.all(
                color: PtwColors.textOnAccent.withValues(alpha: 0.28),
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x66000000),
                  blurRadius: 22,
                  offset: Offset(0, 10),
                ),
              ],
            ),
            clipBehavior: Clip.antiAlias,
            child: EditablePtwStoryCard(
              key: const ValueKey(ComponentIds.sharePreview),
              controller: controller,
              selectedText: selectedText,
              onTextSelected: onTextSelected,
              onCanvasTap: onCanvasTap,
              onStickerSelected: onStickerSelected,
            ),
          ),
        );
      },
    ),
  );
}

final class _ToolSelector extends StatelessWidget {
  const _ToolSelector({required this.selected, required this.onSelected});

  final _StoryBuilderTool selected;
  final ValueChanged<_StoryBuilderTool> onSelected;

  @override
  Widget build(BuildContext context) => Container(
    height: 50,
    padding: const EdgeInsets.fromLTRB(12, 5, 12, 5),
    color: const Color(0xFF10182A),
    child: Row(
      children: [
        Expanded(
          child: _ToolButton(
            key: const ValueKey(ComponentIds.shareEditText),
            label: 'Text',
            icon: Icons.text_fields_rounded,
            selected: selected == _StoryBuilderTool.text,
            onTap: () => onSelected(_StoryBuilderTool.text),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _ToolButton(
            key: const ValueKey(ComponentIds.storyToolLooks),
            label: 'Looks',
            icon: Icons.palette_outlined,
            selected: selected == _StoryBuilderTool.looks,
            onTap: () => onSelected(_StoryBuilderTool.looks),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _ToolButton(
            key: const ValueKey(ComponentIds.storyToolStickers),
            label: 'Stickers',
            icon: Icons.emoji_emotions_outlined,
            selected: selected == _StoryBuilderTool.stickers,
            onTap: () => onSelected(_StoryBuilderTool.stickers),
          ),
        ),
      ],
    ),
  );
}

final class _ToolButton extends StatelessWidget {
  const _ToolButton({
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
    color: selected ? PtwColors.hotPink : const Color(0xFF202A44),
    borderRadius: BorderRadius.circular(999),
    child: InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 17, color: PtwColors.textOnAccent),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(
              color: PtwColors.textOnAccent,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    ),
  );
}

final class _TextTool extends StatelessWidget {
  const _TextTool({
    required this.headline,
    required this.dare,
    required this.headlineFocus,
    required this.dareFocus,
    required this.selectedText,
    required this.headlineInvalid,
    required this.dareInvalid,
    required this.onHeadlineTap,
    required this.onDareTap,
    required this.onChanged,
    required this.onDone,
  });

  final TextEditingController headline;
  final TextEditingController dare;
  final FocusNode headlineFocus;
  final FocusNode dareFocus;
  final PtwStoryTextTarget? selectedText;
  final bool headlineInvalid;
  final bool dareInvalid;
  final VoidCallback onHeadlineTap;
  final VoidCallback onDareTap;
  final VoidCallback onChanged;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(12, 7, 12, 6),
    child: Column(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                headlineInvalid || dareInvalid
                    ? 'Both Story lines are required.'
                    : 'Story-only text · your project stays unchanged',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color:
                      headlineInvalid || dareInvalid
                          ? PtwColors.accentPink
                          : PtwColors.softWhite,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            TextButton(
              key: const ValueKey(ComponentIds.storyEditorDone),
              onPressed: onDone,
              style: TextButton.styleFrom(
                foregroundColor: PtwColors.accentYellow,
                visualDensity: VisualDensity.compact,
              ),
              child: const Text('Done'),
            ),
          ],
        ),
        Row(
          children: [
            Expanded(
              child: _StoryTextField(
                key: const ValueKey(ComponentIds.storyHeadlineField),
                label: 'Headline',
                controller: headline,
                focusNode: headlineFocus,
                maximumLength: PtwStoryComposition.maximumHeadlineLength,
                selected: selectedText == PtwStoryTextTarget.headline,
                invalid: headlineInvalid,
                onTap: onHeadlineTap,
                onChanged: onChanged,
              ),
            ),
            const SizedBox(width: 9),
            Expanded(
              child: _StoryTextField(
                key: const ValueKey(ComponentIds.storyDareField),
                label: 'Short dare',
                controller: dare,
                focusNode: dareFocus,
                maximumLength: PtwStoryComposition.maximumDareLength,
                selected: selectedText == PtwStoryTextTarget.dare,
                invalid: dareInvalid,
                onTap: onDareTap,
                onChanged: onChanged,
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

final class _StoryTextField extends StatelessWidget {
  const _StoryTextField({
    required this.label,
    required this.controller,
    required this.focusNode,
    required this.maximumLength,
    required this.selected,
    required this.invalid,
    required this.onTap,
    required this.onChanged,
    super.key,
  });

  final String label;
  final TextEditingController controller;
  final FocusNode focusNode;
  final int maximumLength;
  final bool selected;
  final bool invalid;
  final VoidCallback onTap;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) => TextField(
    controller: controller,
    focusNode: focusNode,
    maxLength: maximumLength,
    maxLines: 1,
    textInputAction: TextInputAction.done,
    inputFormatters: [LengthLimitingTextInputFormatter(maximumLength)],
    onTap: onTap,
    onChanged: (_) => onChanged(),
    onSubmitted: (_) => focusNode.unfocus(),
    style: const TextStyle(
      color: PtwColors.textOnAccent,
      fontSize: 14,
      fontWeight: FontWeight.w700,
    ),
    decoration: InputDecoration(
      labelText: label,
      counterText: '',
      isDense: true,
      filled: true,
      fillColor: const Color(0xFF0F1627),
      labelStyle: TextStyle(
        color: invalid ? PtwColors.accentPink : PtwColors.softWhite,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(13),
        borderSide: BorderSide(
          color:
              invalid
                  ? PtwColors.accentPink
                  : selected
                  ? PtwColors.accentYellow
                  : const Color(0xFF39435F),
          width: selected || invalid ? 2 : 1,
        ),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(13),
        borderSide: const BorderSide(color: PtwColors.accentYellow, width: 2),
      ),
    ),
  );
}

final class _LooksTool extends StatelessWidget {
  const _LooksTool({required this.controller, required this.onApply});

  final PtwStoryConstructorController controller;
  final VoidCallback onApply;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(10, 8, 10, 6),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 38,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: PtwStoryLooks.all.length,
            separatorBuilder: (_, __) => const SizedBox(width: 7),
            itemBuilder: (context, index) {
              final preset = PtwStoryLooks.all[index];
              return ChoiceChip(
                key: ValueKey('story_look_${preset.id}'),
                label: Text(preset.label),
                selected: controller.composition.lookId == preset.id,
                showCheckmark: false,
                onSelected: (_) {
                  onApply();
                  controller.applyLook(preset);
                },
                selectedColor: PtwColors.hotPink,
                labelStyle: TextStyle(
                  color:
                      controller.composition.lookId == preset.id
                          ? PtwColors.textOnAccent
                          : PtwColors.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 7),
        Expanded(
          child: ListView.separated(
            key: const ValueKey('story_background_tray'),
            scrollDirection: Axis.horizontal,
            itemCount: StudioBackgrounds.all.length + 1,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              if (index == 0) {
                return _BackgroundTile(
                  label: 'Project',
                  selected: controller.composition.backgroundId == null,
                  onTap: () {
                    onApply();
                    controller.selectProjectBackground();
                  },
                  child: PtwMediaImage(
                    image: controller.composition.projectBackground,
                  ),
                );
              }
              final background = StudioBackgrounds.all[index - 1];
              return _BackgroundTile(
                key: ValueKey('story_background_${background.id}'),
                label: background.label,
                selected: controller.composition.backgroundId == background.id,
                onTap: () {
                  onApply();
                  controller.selectBackground(background.id);
                },
                child: switch (background.kind) {
                  StudioBackgroundKind.gradient => DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: background.colors),
                    ),
                  ),
                  StudioBackgroundKind.image => Image.asset(
                    background.assetPath!,
                    fit: BoxFit.cover,
                  ),
                },
              );
            },
          ),
        ),
      ],
    ),
  );
}

final class _BackgroundTile extends StatelessWidget {
  const _BackgroundTile({
    required this.label,
    required this.selected,
    required this.onTap,
    required this.child,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 58,
    child: InkWell(
      borderRadius: BorderRadius.circular(11),
      onTap: onTap,
      child: Column(
        children: [
          Expanded(
            child: Container(
              clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(11),
                border: Border.all(
                  color:
                      selected
                          ? PtwColors.accentYellow
                          : const Color(0xFF46516F),
                  width: selected ? 3 : 1,
                ),
              ),
              child: SizedBox.expand(child: child),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: PtwColors.softWhite,
              fontSize: 9.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    ),
  );
}

final class _StickersTool extends StatelessWidget {
  const _StickersTool({
    required this.controller,
    required this.category,
    required this.onCategoryChanged,
    required this.onAdd,
  });

  final PtwStoryConstructorController controller;
  final MemeStickerCategory category;
  final ValueChanged<MemeStickerCategory> onCategoryChanged;
  final ValueChanged<String> onAdd;

  @override
  Widget build(BuildContext context) {
    final stickers = controller.catalog.inCategory(category);
    final atLimit = !controller.canAddSticker;
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 7, 10, 6),
      child: Column(
        children: [
          Row(
            children: [
              for (final item in MemeStickerCategory.values) ...[
                _CategoryButton(
                  category: item,
                  selected: category == item,
                  onTap: () => onCategoryChanged(item),
                ),
                const SizedBox(width: 6),
              ],
              const Spacer(),
              Text(
                atLimit
                    ? '3/3 · Delete one to add'
                    : '${controller.composition.stickers.length}/3',
                style: TextStyle(
                  color: atLimit ? PtwColors.accentPink : PtwColors.softWhite,
                  fontSize: 11,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.separated(
              key: const ValueKey(ComponentIds.storyStickerTray),
              scrollDirection: Axis.horizontal,
              itemCount: stickers.length,
              separatorBuilder: (_, __) => const SizedBox(width: 9),
              itemBuilder: (context, index) {
                final sticker = stickers[index];
                return Tooltip(
                  message: sticker.label,
                  child: Semantics(
                    button: true,
                    enabled: !atLimit,
                    label: 'Add ${sticker.label} sticker',
                    child: InkWell(
                      key: ValueKey('story_sticker_${sticker.id}'),
                      borderRadius: BorderRadius.circular(14),
                      onTap: atLimit ? null : () => onAdd(sticker.id),
                      child: AnimatedOpacity(
                        opacity: atLimit ? 0.38 : 1,
                        duration: const Duration(milliseconds: 120),
                        child: Container(
                          width: 72,
                          padding: const EdgeInsets.all(7),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0F1627),
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: const Color(0xFF39435F)),
                          ),
                          child: Image.asset(
                            sticker.assetPath,
                            fit: BoxFit.contain,
                            filterQuality: FilterQuality.high,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

final class _CategoryButton extends StatelessWidget {
  const _CategoryButton({
    required this.category,
    required this.selected,
    required this.onTap,
  });

  final MemeStickerCategory category;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: selected ? PtwColors.hotPink : const Color(0xFF29334E),
    borderRadius: BorderRadius.circular(999),
    child: InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Text(
          category.label,
          style: const TextStyle(
            color: PtwColors.textOnAccent,
            fontSize: 11,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    ),
  );
}
