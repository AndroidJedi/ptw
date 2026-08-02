import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_action_sheet.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_pinned_action_bar.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

enum _ShareAction { stories, copy, instagram, tiktok, more }

final class ShareStoryPreviewScreen extends StatelessWidget {
  const ShareStoryPreviewScreen({required this.projectId, super.key});

  final String projectId;

  void _prepared(BuildContext context, String platform) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Project card prepared for $platform')),
    );
  }

  Future<void> _openActions(BuildContext context, String link) async {
    final action = await showPtwActionSheet<_ShareAction>(
      context,
      actions: const [
        PtwActionSheetItem(
          id: ComponentIds.shareActionStories,
          label: 'Share to Stories',
          value: _ShareAction.stories,
        ),
        PtwActionSheetItem(
          id: ComponentIds.shareCopyLink,
          label: 'Copy link',
          value: _ShareAction.copy,
        ),
        PtwActionSheetItem(
          id: ComponentIds.shareActionInstagram,
          label: 'Instagram',
          value: _ShareAction.instagram,
        ),
        PtwActionSheetItem(
          id: ComponentIds.shareActionTiktok,
          label: 'TikTok',
          value: _ShareAction.tiktok,
        ),
        PtwActionSheetItem(
          id: ComponentIds.shareActionMore,
          label: 'More',
          value: _ShareAction.more,
        ),
      ],
    );
    if (action == null || !context.mounted) return;
    switch (action) {
      case _ShareAction.stories:
        _prepared(context, 'Stories');
        break;
      case _ShareAction.copy:
        await Clipboard.setData(ClipboardData(text: link));
        if (context.mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Link copied')));
        }
        break;
      case _ShareAction.instagram:
        _prepared(context, 'Instagram');
        break;
      case _ShareAction.tiktok:
        _prepared(context, 'TikTok');
        break;
      case _ShareAction.more:
        _prepared(context, 'other apps');
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(projectId);
    if (project == null) {
      return PtwImmersivePage(
        child: Column(
          children: [
            const Align(
              alignment: Alignment.centerLeft,
              child: PtwBackButton(fallbackRoute: '/'),
            ),
            Expanded(
              child: Center(
                child: const PtwStickerText.hero(
                  'Project unavailable',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        ),
      );
    }
    final link = 'https://ptw.to/${project.ownerHandle}';
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
                PtwProjectTile(project: project, height: 410),
                const SizedBox(height: PtwSpacing.md),
                Text(
                  'PTW.TO/${project.ownerHandle.toUpperCase()}',
                  textAlign: TextAlign.center,
                  style: PtwTypography.bodyStrong.copyWith(
                    color: PtwColors.textOnAccent,
                  ),
                ),
              ],
            ),
          ),
          PtwPinnedActionBar(
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.sharePrimary),
              label: 'Share to Stories',
              icon: Icons.auto_awesome_rounded,
              onPressed: () => _openActions(context, link),
            ),
          ),
        ],
      ),
    );
  }
}
