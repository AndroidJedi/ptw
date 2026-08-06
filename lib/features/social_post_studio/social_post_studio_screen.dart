import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_typography.dart';
import 'social_post_studio_controller.dart';
import 'story_post_card.dart';
import 'studio_avatar_picker.dart';
import 'studio_models.dart';

final class SocialPostStudioScreen extends StatefulWidget {
  const SocialPostStudioScreen({
    required this.catalog,
    super.key,
    this.controller,
    this.avatarPicker,
  });

  final MemeStickerCatalog catalog;
  final SocialPostStudioController? controller;
  final StudioAvatarPicker? avatarPicker;

  @override
  State<SocialPostStudioScreen> createState() => _SocialPostStudioScreenState();
}

final class _SocialPostStudioScreenState extends State<SocialPostStudioScreen> {
  late final SocialPostStudioController _controller;
  late final bool _ownsController;
  late final StudioAvatarPicker _avatarPicker;
  late final TextEditingController _messageController;
  bool _pickingAvatar = false;
  String? _avatarError;

  @override
  void initState() {
    super.initState();
    _ownsController = widget.controller == null;
    _controller =
        widget.controller ??
        SocialPostStudioController(catalog: widget.catalog);
    _avatarPicker = widget.avatarPicker ?? BrowserStudioAvatarPicker();
    _messageController = TextEditingController(text: _controller.draft.message);
  }

  @override
  void dispose() {
    _messageController.dispose();
    if (_ownsController) _controller.dispose();
    super.dispose();
  }

  Future<void> _pickAvatar() async {
    if (_pickingAvatar) return;
    setState(() {
      _pickingAvatar = true;
      _avatarError = null;
    });
    try {
      final selection = await _avatarPicker.pickAvatar();
      if (selection != null) _controller.setAvatarBytes(selection.bytes);
    } on StudioAvatarPickException catch (error) {
      if (mounted) setState(() => _avatarError = error.message);
    } on Object {
      if (mounted) {
        setState(() => _avatarError = 'That image could not be opened.');
      }
    } finally {
      if (mounted) setState(() => _pickingAvatar = false);
    }
  }

  void _reset() {
    _controller.reset();
    _messageController.value = TextEditingValue(
      text: _controller.draft.message,
      selection: TextSelection.collapsed(
        offset: _controller.draft.message.length,
      ),
    );
    setState(() => _avatarError = null);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    key: const ValueKey('social_post_studio_screen'),
    backgroundColor: PtwColors.backgroundPrimary,
    body: SafeArea(
      child: Column(
        children: [
          _StudioHeader(onReset: _reset),
          Expanded(
            child: AnimatedBuilder(
              animation: _controller,
              builder:
                  (context, _) => LayoutBuilder(
                    builder: (context, constraints) {
                      if (constraints.maxWidth >= 1050) {
                        return _DesktopStudio(
                          controller: _controller,
                          messageController: _messageController,
                          pickingAvatar: _pickingAvatar,
                          avatarError: _avatarError,
                          onPickAvatar: _pickAvatar,
                        );
                      }
                      return _CompactStudio(
                        controller: _controller,
                        messageController: _messageController,
                        pickingAvatar: _pickingAvatar,
                        avatarError: _avatarError,
                        onPickAvatar: _pickAvatar,
                      );
                    },
                  ),
            ),
          ),
        ],
      ),
    ),
  );
}

final class _StudioHeader extends StatelessWidget {
  const _StudioHeader({required this.onReset});

  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) => Container(
    height: 70,
    padding: const EdgeInsets.symmetric(horizontal: 22),
    decoration: const BoxDecoration(
      color: PtwColors.surfacePrimary,
      border: Border(bottom: BorderSide(color: PtwColors.borderDefault)),
    ),
    child: Row(
      children: [
        Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            color: PtwColors.hotPink,
            shape: BoxShape.circle,
          ),
          child: const Text(
            'P',
            style: TextStyle(
              color: PtwColors.textOnAccent,
              fontFamily: 'PtwLilitaOne',
              fontSize: 24,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Story Studio', style: PtwTypography.title),
              Text(
                'Local prototype · changes reset on reload',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PtwTypography.caption,
              ),
            ],
          ),
        ),
        TextButton.icon(
          key: const ValueKey('studio_reset'),
          onPressed: onReset,
          icon: const Icon(Icons.refresh_rounded, size: 19),
          label: const Text('Reset'),
          style: TextButton.styleFrom(foregroundColor: PtwColors.textPrimary),
        ),
      ],
    ),
  );
}

final class _DesktopStudio extends StatelessWidget {
  const _DesktopStudio({
    required this.controller,
    required this.messageController,
    required this.pickingAvatar,
    required this.avatarError,
    required this.onPickAvatar,
  });

  final SocialPostStudioController controller;
  final TextEditingController messageController;
  final bool pickingAvatar;
  final String? avatarError;
  final VoidCallback onPickAvatar;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(18),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 294,
          child: SingleChildScrollView(
            child: _ContentPanel(
              controller: controller,
              messageController: messageController,
              pickingAvatar: pickingAvatar,
              avatarError: avatarError,
              onPickAvatar: onPickAvatar,
            ),
          ),
        ),
        const SizedBox(width: 18),
        Expanded(child: _CanvasPanel(controller: controller)),
        const SizedBox(width: 18),
        SizedBox(
          width: 330,
          child: SingleChildScrollView(
            child: _StickerPanel(controller: controller),
          ),
        ),
      ],
    ),
  );
}

final class _CompactStudio extends StatelessWidget {
  const _CompactStudio({
    required this.controller,
    required this.messageController,
    required this.pickingAvatar,
    required this.avatarError,
    required this.onPickAvatar,
  });

  final SocialPostStudioController controller;
  final TextEditingController messageController;
  final bool pickingAvatar;
  final String? avatarError;
  final VoidCallback onPickAvatar;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _CanvasPanel(controller: controller, compact: true),
      const SizedBox(height: 14),
      _ContentPanel(
        controller: controller,
        messageController: messageController,
        pickingAvatar: pickingAvatar,
        avatarError: avatarError,
        onPickAvatar: onPickAvatar,
      ),
      const SizedBox(height: 14),
      _StickerPanel(controller: controller),
    ],
  );
}

final class _ContentPanel extends StatelessWidget {
  const _ContentPanel({
    required this.controller,
    required this.messageController,
    required this.pickingAvatar,
    required this.avatarError,
    required this.onPickAvatar,
  });

  final SocialPostStudioController controller;
  final TextEditingController messageController;
  final bool pickingAvatar;
  final String? avatarError;
  final VoidCallback onPickAvatar;

  @override
  Widget build(BuildContext context) => _Panel(
    title: 'Card content',
    subtitle: 'Keep it short, direct, and worth replying to.',
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          key: const ValueKey('studio_message'),
          controller: messageController,
          maxLength: SocialPostStudioController.maximumMessageLength,
          minLines: 2,
          maxLines: 4,
          textCapitalization: TextCapitalization.sentences,
          onChanged: controller.updateMessage,
          decoration: const InputDecoration(
            labelText: 'Message',
            alignLabelWithHint: true,
            counterStyle: TextStyle(color: PtwColors.textMuted),
          ),
        ),
        const SizedBox(height: 12),
        Text('AVATAR', style: _sectionLabelStyle),
        const SizedBox(height: 8),
        Row(
          children: [
            _AvatarPreview(image: controller.draft.avatar),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton(
                key: const ValueKey('studio_pick_avatar'),
                onPressed: pickingAvatar ? null : onPickAvatar,
                child: Text(pickingAvatar ? 'Opening…' : 'Change avatar'),
              ),
            ),
          ],
        ),
        if (avatarError != null) ...[
          const SizedBox(height: 7),
          Text(
            avatarError!,
            key: const ValueKey('studio_avatar_error'),
            style: PtwTypography.caption.copyWith(color: PtwColors.hotPink),
          ),
        ],
        const SizedBox(height: 18),
        Text('BACKGROUND', style: _sectionLabelStyle),
        const SizedBox(height: 8),
        GridView.builder(
          key: const ValueKey('studio_backgrounds'),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: StudioBackgrounds.all.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            childAspectRatio: 1.28,
          ),
          itemBuilder: (context, index) {
            final background = StudioBackgrounds.all[index];
            final selected = background.id == controller.draft.backgroundId;
            return Tooltip(
              message: background.label,
              child: InkWell(
                key: ValueKey('studio_background_${background.id}'),
                onTap: () => controller.selectBackground(background.id),
                borderRadius: BorderRadius.circular(12),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color:
                          selected
                              ? PtwColors.hotPink
                              : PtwColors.borderDefault,
                      width: selected ? 3 : 1,
                    ),
                  ),
                  child: _BackgroundThumbnail(definition: background),
                ),
              ),
            );
          },
        ),
      ],
    ),
  );
}

final class _CanvasPanel extends StatelessWidget {
  const _CanvasPanel({required this.controller, this.compact = false});

  final SocialPostStudioController controller;
  final bool compact;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final inferredHeight =
          (constraints.maxWidth - 28) / StoryPostCard.logicalSize.aspectRatio +
          66;
      final panelHeight =
          compact ? math.min(720.0, inferredHeight) : constraints.maxHeight;
      return SizedBox(
        height: panelHeight,
        child: _Panel(
          title: 'Story preview',
          subtitle: 'Drag stickers. Use the pink handle to resize and rotate.',
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 14),
          child: Expanded(
            child: LayoutBuilder(
              builder: (context, previewConstraints) {
                final availableWidth = previewConstraints.maxWidth;
                final availableHeight = previewConstraints.maxHeight;
                final scale = math.min(
                  availableWidth / StoryPostCard.logicalSize.width,
                  availableHeight / StoryPostCard.logicalSize.height,
                );
                return Center(
                  child: Container(
                    width: StoryPostCard.logicalSize.width * scale,
                    height: StoryPostCard.logicalSize.height * scale,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(26),
                      border: Border.all(
                        color: PtwColors.surfacePrimary,
                        width: 2,
                      ),
                      boxShadow: const [
                        BoxShadow(
                          color: PtwColors.shadow,
                          blurRadius: 24,
                          offset: Offset(0, 12),
                        ),
                      ],
                    ),
                    child: FittedBox(
                      fit: BoxFit.fill,
                      child: SizedBox(
                        width: StoryPostCard.logicalSize.width,
                        height: StoryPostCard.logicalSize.height,
                        child: EditableStoryPostCard(controller: controller),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );
    },
  );
}

final class _StickerPanel extends StatelessWidget {
  const _StickerPanel({required this.controller});

  final SocialPostStudioController controller;

  @override
  Widget build(BuildContext context) {
    final selected = controller.selectedPlacement;
    final selectedIndex =
        selected == null ? -1 : controller.draft.stickers.indexOf(selected);
    return _Panel(
      title: 'Reaction stickers',
      subtitle:
          '${controller.draft.stickers.length}/${SocialPostStudioController.maximumStickerCount} layers',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: 7,
            children: [
              for (final category in MemeStickerCategory.values)
                ChoiceChip(
                  key: ValueKey('studio_category_${category.name}'),
                  label: Text(category.label),
                  selected: controller.category == category,
                  showCheckmark: false,
                  onSelected: (_) => controller.selectCategory(category),
                  selectedColor: PtwColors.hotPink,
                  labelStyle: TextStyle(
                    color:
                        controller.category == category
                            ? PtwColors.textOnAccent
                            : PtwColors.textPrimary,
                    fontWeight: FontWeight.w800,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          GridView.builder(
            key: const ValueKey('studio_sticker_grid'),
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: controller.visibleStickers.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 4,
              crossAxisSpacing: 7,
              mainAxisSpacing: 7,
            ),
            itemBuilder: (context, index) {
              final sticker = controller.visibleStickers[index];
              return Tooltip(
                message: sticker.label,
                child: InkWell(
                  key: ValueKey('studio_add_${sticker.id}'),
                  onTap:
                      controller.canAddSticker
                          ? () => controller.addSticker(sticker.id)
                          : null,
                  borderRadius: BorderRadius.circular(14),
                  child: AnimatedOpacity(
                    opacity: controller.canAddSticker ? 1 : 0.4,
                    duration: const Duration(milliseconds: 120),
                    child: Container(
                      padding: const EdgeInsets.all(5),
                      decoration: BoxDecoration(
                        color: PtwColors.backgroundSecondary,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: PtwColors.borderDefault),
                      ),
                      child: Image.asset(sticker.assetPath),
                    ),
                  ),
                ),
              );
            },
          ),
          if (!controller.canAddSticker) ...[
            const SizedBox(height: 8),
            Text(
              'Three stickers max. Remove a layer to add another.',
              key: const ValueKey('studio_sticker_limit'),
              style: PtwTypography.caption.copyWith(
                color: PtwColors.hotPink,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 18),
          Text('LAYERS', style: _sectionLabelStyle),
          const SizedBox(height: 7),
          if (controller.draft.stickers.isEmpty)
            Text(
              'Choose a reaction above to place it on the Story.',
              style: PtwTypography.caption,
            )
          else
            for (final placement in controller.draft.stickers.reversed)
              _LayerRow(
                placement: placement,
                definition: controller.catalog.byId(placement.stickerId),
                selected: placement.instanceId == controller.selectedStickerId,
                onTap: () => controller.selectSticker(placement.instanceId),
              ),
          if (selected != null) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: [
                IconButton.filledTonal(
                  key: const ValueKey('studio_layer_backward'),
                  tooltip: 'Move backward',
                  onPressed:
                      selectedIndex > 0
                          ? controller.moveSelectedBackward
                          : null,
                  icon: const Icon(Icons.flip_to_back_rounded),
                ),
                IconButton.filledTonal(
                  key: const ValueKey('studio_layer_forward'),
                  tooltip: 'Move forward',
                  onPressed:
                      selectedIndex >= 0 &&
                              selectedIndex <
                                  controller.draft.stickers.length - 1
                          ? controller.moveSelectedForward
                          : null,
                  icon: const Icon(Icons.flip_to_front_rounded),
                ),
                IconButton.filledTonal(
                  key: const ValueKey('studio_layer_duplicate'),
                  tooltip: 'Duplicate',
                  onPressed:
                      controller.canAddSticker
                          ? controller.duplicateSelected
                          : null,
                  icon: const Icon(Icons.copy_rounded),
                ),
                IconButton.filledTonal(
                  key: const ValueKey('studio_layer_delete'),
                  tooltip: 'Delete',
                  onPressed: controller.removeSelected,
                  icon: const Icon(Icons.delete_outline_rounded),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Arrow keys nudge · Shift moves faster · Delete removes',
              style: PtwTypography.caption,
            ),
          ],
        ],
      ),
    );
  }
}

final class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.subtitle,
    required this.child,
    this.padding = const EdgeInsets.all(18),
  });

  final String title;
  final String subtitle;
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: PtwColors.surfacePrimary,
      borderRadius: BorderRadius.circular(24),
      border: Border.all(color: PtwColors.borderDefault),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0D272334),
          blurRadius: 18,
          offset: Offset(0, 8),
        ),
      ],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(title, style: PtwTypography.title),
        const SizedBox(height: 3),
        Text(subtitle, style: PtwTypography.caption),
        const SizedBox(height: 16),
        child,
      ],
    ),
  );
}

final class _AvatarPreview extends StatelessWidget {
  const _AvatarPreview({required this.image});

  final StudioImageRef image;

  @override
  Widget build(BuildContext context) => Container(
    width: 54,
    height: 54,
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      border: Border.all(color: PtwColors.borderDefault),
    ),
    child: switch (image.source) {
      StudioImageSource.asset => Image.asset(image.path!, fit: BoxFit.cover),
      StudioImageSource.memory => Image.memory(
        image.bytes!,
        fit: BoxFit.cover,
        gaplessPlayback: true,
      ),
    },
  );
}

final class _BackgroundThumbnail extends StatelessWidget {
  const _BackgroundThumbnail({required this.definition});

  final StudioBackgroundDefinition definition;

  @override
  Widget build(BuildContext context) =>
      definition.kind == StudioBackgroundKind.image
          ? Image.asset(definition.assetPath!, fit: BoxFit.cover)
          : DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: definition.colors),
            ),
          );
}

final class _LayerRow extends StatelessWidget {
  const _LayerRow({
    required this.placement,
    required this.definition,
    required this.selected,
    required this.onTap,
  });

  final StickerPlacement placement;
  final MemeStickerDefinition definition;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 6),
    child: InkWell(
      key: ValueKey('studio_layer_${placement.instanceId}'),
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
        decoration: BoxDecoration(
          color:
              selected
                  ? PtwColors.surfaceLavender
                  : PtwColors.backgroundPrimary,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? PtwColors.accentPurple : PtwColors.borderDefault,
          ),
        ),
        child: Row(
          children: [
            Image.asset(definition.assetPath, width: 34, height: 34),
            const SizedBox(width: 9),
            Expanded(child: Text(definition.label, style: PtwTypography.label)),
            Icon(
              selected ? Icons.check_circle_rounded : Icons.drag_indicator,
              size: 18,
              color: selected ? PtwColors.accentPurple : PtwColors.textMuted,
            ),
          ],
        ),
      ),
    ),
  );
}

const _sectionLabelStyle = TextStyle(
  color: PtwColors.textMuted,
  fontFamily: 'PtwRoboto',
  fontSize: 11,
  fontWeight: FontWeight.w900,
  letterSpacing: 1.1,
);
