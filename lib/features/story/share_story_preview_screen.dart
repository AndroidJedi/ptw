import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../features/share/share_asset_generator.dart';
import '../../features/share/share_card.dart';
import '../../features/share/share_controller.dart';
import '../../features/share/share_engine.dart';
import '../../features/share/share_guide.dart';
import '../../features/share/share_models.dart';
import '../../features/share/share_platform_style.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';

final class ShareStoryPreviewScreen extends StatefulWidget {
  const ShareStoryPreviewScreen({
    required this.projectId,
    super.key,
    this.event = ShareEvent.manual,
    this.initialTemplate,
  });

  final String projectId;
  final ShareEvent event;
  final ShareTemplateType? initialTemplate;

  @override
  State<ShareStoryPreviewScreen> createState() =>
      _ShareStoryPreviewScreenState();
}

final class _ShareStoryPreviewScreenState
    extends State<ShareStoryPreviewScreen> {
  final _assetGenerator = const ShareAssetGenerator();
  ShareController? _controller;
  bool _preparing = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_controller != null) return;
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(widget.projectId);
    if (project == null) return;
    _controller = ShareController(
      engine: ShareEngine(catalog: state.shareCatalog),
      project: project,
      responses: state.responsesFor(project.id),
      evidence: state.evidenceFor(project.id),
      referenceTime: state.now,
      event: widget.event,
      initialTemplate: widget.initialTemplate,
    )..addListener(_onControllerChanged);
  }

  @override
  void dispose() {
    _controller?.removeListener(_onControllerChanged);
    _controller?.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _copy(String value, String message) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _editText() async {
    final controller = _controller!;
    final result = await showModalBottomSheet<({String hook, String caption})>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PtwColors.surfacePrimary,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(PtwRadius.xl)),
      ),
      builder:
          (context) => _EditCopySheet(
            initialHook: controller.card.hook,
            initialCaption: controller.card.caption,
          ),
    );
    if (result == null) return;
    controller.editCopy(hook: result.hook, caption: result.caption);
  }

  Future<void> _share() async {
    if (_preparing) return;
    final controller = _controller!;
    setState(() => _preparing = true);
    try {
      final asset = await _assetGenerator.generate(
        context: context,
        data: controller.card,
        format: controller.format,
      );
      if (!mounted) return;
      await showPtwShareGuide(
        context: context,
        asset: asset,
        card: controller.card,
        guide: controller.engine.catalog.guide(controller.platform),
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('The share card is still preparing.')),
      );
    } finally {
      if (mounted) setState(() => _preparing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    if (state.maybeProjectById(widget.projectId) == null ||
        _controller == null) {
      return const _MissingProject();
    }
    final controller = _controller!;
    final card = controller.card;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.shareScreen),
      child: Column(
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: PtwBackButton(
              key: ValueKey(ComponentIds.shareBack),
              fallbackRoute: '/',
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PtwSpacing.screenHorizontal,
                PtwSpacing.xs,
                PtwSpacing.screenHorizontal,
                PtwSpacing.md,
              ),
              children: [
                const PtwStickerText.hero(
                  'Get Your First Doubts',
                  key: ValueKey(ComponentIds.shareTitle),
                ),
                const SizedBox(height: PtwSpacing.lg),
                _ShareCardPreview(data: card, format: controller.format),
                if (card.usesFallbackData) ...[
                  const SizedBox(height: PtwSpacing.xs),
                  Text(
                    'DEMO DATA · PREVIEW ONLY',
                    key: const ValueKey(ComponentIds.shareDemoData),
                    textAlign: TextAlign.center,
                    style: PtwTypography.caption.copyWith(
                      color: PtwColors.textOnAccent,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1,
                    ),
                  ),
                ],
                const SizedBox(height: PtwSpacing.md),
                _TemplateSelector(controller: controller),
                const SizedBox(height: PtwSpacing.md),
                _FormatSelector(controller: controller),
                const SizedBox(height: PtwSpacing.sm),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: PtwSpacing.xs,
                  runSpacing: PtwSpacing.xxs,
                  children: [
                    _InlineAction(
                      key: const ValueKey(ComponentIds.shareEditText),
                      icon: Icons.edit_rounded,
                      label: 'Edit text',
                      onTap: _editText,
                    ),
                    _InlineAction(
                      key: const ValueKey(ComponentIds.shareGenerateAnother),
                      icon: Icons.auto_awesome_rounded,
                      label: 'Another',
                      onTap: controller.generateAnother,
                    ),
                    _InlineAction(
                      key: const ValueKey(ComponentIds.shareCopyLink),
                      icon: Icons.link_rounded,
                      label: 'Copy link',
                      onTap: () => _copy(card.publicLink, 'Link copied'),
                    ),
                    _InlineAction(
                      key: const ValueKey(ComponentIds.shareCopyCaption),
                      icon: Icons.notes_rounded,
                      label: 'Caption',
                      onTap:
                          () => _copy(
                            controller.captionWithLink,
                            'Caption copied',
                          ),
                    ),
                  ],
                ),
                const SizedBox(height: PtwSpacing.lg),
                Text(
                  'SHARE TO',
                  style: PtwTypography.caption.copyWith(
                    color: PtwColors.textOnAccent,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.1,
                  ),
                ),
                const SizedBox(height: PtwSpacing.xs),
                _PlatformSelector(controller: controller),
                const SizedBox(height: PtwSpacing.sm),
              ],
            ),
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.sharePrimary),
              label:
                  _preparing
                      ? 'Preparing card'
                      : 'Share to ${controller.platform.compactLabel}',
              onPressed: _preparing ? null : _share,
            ),
          ),
        ],
      ),
    );
  }
}

final class _ShareCardPreview extends StatelessWidget {
  const _ShareCardPreview({required this.data, required this.format});

  final ShareCardData data;
  final ShareFormat format;

  @override
  Widget build(BuildContext context) {
    final logicalHeight = 360 / format.aspectRatio;
    final previewHeight = switch (format) {
      ShareFormat.story => 430.0,
      ShareFormat.portrait => 410.0,
      ShareFormat.square => 345.0,
    };
    return Container(
      key: const ValueKey(ComponentIds.sharePreview),
      height: previewHeight,
      width: double.infinity,
      alignment: Alignment.center,
      child: FittedBox(
        fit: BoxFit.contain,
        child: RepaintBoundary(
          child: SizedBox(
            width: 360,
            height: logicalHeight,
            child: ShareCard(data: data, format: format),
          ),
        ),
      ),
    );
  }
}

final class _TemplateSelector extends StatelessWidget {
  const _TemplateSelector({required this.controller});

  final ShareController controller;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 42,
    child: ListView.separated(
      key: const ValueKey(ComponentIds.shareTemplateSelector),
      scrollDirection: Axis.horizontal,
      itemCount: ShareTemplateType.values.length,
      separatorBuilder: (_, __) => const SizedBox(width: PtwSpacing.xs),
      itemBuilder: (context, index) {
        final type = ShareTemplateType.values[index];
        final selected = type == controller.template;
        return ChoiceChip(
          key: ValueKey('share_template_${type.name}'),
          selected: selected,
          onSelected: (_) => controller.selectTemplate(type),
          showCheckmark: false,
          label: Text(type.label),
          labelStyle: PtwTypography.label.copyWith(
            color: selected ? PtwColors.ink : PtwColors.textOnAccent,
          ),
          selectedColor: PtwColors.surfacePrimary,
          backgroundColor: PtwColors.ink.withValues(alpha: 0.24),
          side: const BorderSide(color: PtwColors.textOnAccent),
        );
      },
    ),
  );
}

final class _FormatSelector extends StatelessWidget {
  const _FormatSelector({required this.controller});

  final ShareController controller;

  @override
  Widget build(BuildContext context) => Row(
    key: const ValueKey(ComponentIds.shareFormatSelector),
    children: [
      for (final format in ShareFormat.values) ...[
        if (format != ShareFormat.values.first)
          const SizedBox(width: PtwSpacing.xs),
        Expanded(
          child: InkWell(
            key: ValueKey('share_format_${format.name}'),
            onTap: () => controller.selectFormat(format),
            borderRadius: BorderRadius.circular(PtwRadius.pill),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              padding: const EdgeInsets.symmetric(vertical: 9),
              decoration: BoxDecoration(
                color:
                    controller.format == format
                        ? PtwColors.surfacePrimary
                        : PtwColors.transparent,
                border: Border.all(color: PtwColors.textOnAccent),
                borderRadius: BorderRadius.circular(PtwRadius.pill),
              ),
              child: Column(
                children: [
                  Text(
                    format.label,
                    style: PtwTypography.label.copyWith(
                      color:
                          controller.format == format
                              ? PtwColors.ink
                              : PtwColors.textOnAccent,
                    ),
                  ),
                  Text(
                    format.ratioLabel,
                    style: PtwTypography.caption.copyWith(
                      color:
                          controller.format == format
                              ? PtwColors.textSecondary
                              : PtwColors.softWhite,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ],
  );
}

final class _PlatformSelector extends StatelessWidget {
  const _PlatformSelector({required this.controller});

  final ShareController controller;

  @override
  Widget build(BuildContext context) => SizedBox(
    key: const ValueKey(ComponentIds.sharePlatformSelector),
    height: 74,
    child: ListView.separated(
      scrollDirection: Axis.horizontal,
      itemCount: SharePlatform.values.length,
      separatorBuilder: (_, __) => const SizedBox(width: PtwSpacing.xs),
      itemBuilder: (context, index) {
        final platform = SharePlatform.values[index];
        final selected = platform == controller.platform;
        return Material(
          key: ValueKey('share_platform_${platform.name}'),
          color:
              selected
                  ? PtwColors.surfacePrimary
                  : PtwColors.ink.withValues(alpha: 0.22),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(PtwRadius.lg),
            side: const BorderSide(color: PtwColors.textOnAccent),
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => controller.selectPlatform(platform),
            child: SizedBox(
              width: 84,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    SharePlatformStyle.icon(platform),
                    color: selected ? PtwColors.ink : PtwColors.textOnAccent,
                  ),
                  const SizedBox(height: PtwSpacing.xxs),
                  Text(
                    platform.compactLabel,
                    textAlign: TextAlign.center,
                    style: PtwTypography.caption.copyWith(
                      color: selected ? PtwColors.ink : PtwColors.textOnAccent,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    ),
  );
}

final class _InlineAction extends StatelessWidget {
  const _InlineAction({
    required this.icon,
    required this.label,
    required this.onTap,
    super.key,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => TextButton.icon(
    onPressed: onTap,
    icon: Icon(icon, size: 17),
    label: Text(label),
    style: TextButton.styleFrom(
      foregroundColor: PtwColors.textOnAccent,
      textStyle: PtwTypography.label,
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
    ),
  );
}

final class _EditCopySheet extends StatefulWidget {
  const _EditCopySheet({
    required this.initialHook,
    required this.initialCaption,
  });

  final String initialHook;
  final String initialCaption;

  @override
  State<_EditCopySheet> createState() => _EditCopySheetState();
}

final class _EditCopySheetState extends State<_EditCopySheet> {
  late final TextEditingController _hook;
  late final TextEditingController _caption;

  @override
  void initState() {
    super.initState();
    _hook = TextEditingController(text: widget.initialHook);
    _caption = TextEditingController(text: widget.initialCaption);
  }

  @override
  void dispose() {
    _hook.dispose();
    _caption.dispose();
    super.dispose();
  }

  void _save() {
    final hook = _hook.text.trim();
    final caption = _caption.text.trim();
    if (hook.isEmpty || caption.isEmpty) return;
    Navigator.of(context).pop((hook: hook, caption: caption));
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      PtwSpacing.screenHorizontal,
      PtwSpacing.lg,
      PtwSpacing.screenHorizontal,
      MediaQuery.viewInsetsOf(context).bottom + PtwSpacing.lg,
    ),
    child: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Make it sound like you', style: PtwTypography.titleLarge),
          const SizedBox(height: PtwSpacing.lg),
          TextField(
            key: const ValueKey(ComponentIds.shareEditHook),
            controller: _hook,
            maxLength: 90,
            minLines: 2,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Card text'),
          ),
          const SizedBox(height: PtwSpacing.sm),
          TextField(
            key: const ValueKey(ComponentIds.shareEditCaption),
            controller: _caption,
            maxLength: 280,
            minLines: 3,
            maxLines: 5,
            decoration: const InputDecoration(labelText: 'Caption'),
          ),
          const SizedBox(height: PtwSpacing.md),
          PtwBlackButton(
            key: const ValueKey(ComponentIds.shareEditSave),
            label: 'Use this text',
            onPressed: _save,
          ),
        ],
      ),
    ),
  );
}

final class _MissingProject extends StatelessWidget {
  const _MissingProject();

  @override
  Widget build(BuildContext context) => PtwImmersivePage(
    child: Column(
      children: [
        const Align(
          alignment: Alignment.centerLeft,
          child: PtwBackButton(fallbackRoute: '/'),
        ),
        const Expanded(
          child: Center(
            child: PtwStickerText.hero(
              'Project unavailable',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ],
    ),
  );
}
