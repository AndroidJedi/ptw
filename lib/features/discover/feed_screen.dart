import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_gradients.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_social_activity.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/atoms/ptw_sticker_text.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';

final class FeedScreen extends StatelessWidget {
  const FeedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final activity = PtwScope.of(context).socialActivity;
    final systemPadding = MediaQuery.paddingOf(context);
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.feedScreen),
      safeArea: false,
      child:
          activity.isEmpty
              ? SafeArea(
                child: Column(
                  children: [
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: PtwBackButton(
                        key: ValueKey(ComponentIds.feedBack),
                        fallbackRoute: '/',
                      ),
                    ),
                    Expanded(
                      child: Center(
                        child: Text(
                          'Nothing new yet',
                          style: PtwTypography.titleLarge.copyWith(
                            color: PtwColors.textOnAccent,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              )
              : Stack(
                children: [
                  ListView.separated(
                    key: const ValueKey(ComponentIds.feedList),
                    padding: EdgeInsets.only(
                      bottom: systemPadding.bottom + PtwSpacing.md,
                    ),
                    itemCount: activity.length,
                    separatorBuilder:
                        (_, __) => const SizedBox(height: PtwSpacing.xxs),
                    itemBuilder:
                        (context, index) => _ActivityBand(
                          key: ValueKey(activity[index].id),
                          activity: activity[index],
                          first: index == 0,
                          systemTop: systemPadding.top,
                          onTap:
                              () => context.push(
                                '/p/${activity[index].project.id}',
                              ),
                        ),
                  ),
                  Positioned(
                    left: PtwSpacing.xs,
                    top: systemPadding.top + PtwSpacing.xxs,
                    child: const PtwBackButton(
                      key: ValueKey(ComponentIds.feedBack),
                      fallbackRoute: '/',
                    ),
                  ),
                ],
              ),
    );
  }
}

final class _ActivityBand extends StatelessWidget {
  const _ActivityBand({
    required this.activity,
    required this.first,
    required this.systemTop,
    required this.onTap,
    super.key,
  });

  final PtwSocialActivity activity;
  final bool first;
  final double systemTop;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final primary = Color(activity.project.primaryColor);
    return Semantics(
      button: true,
      label: activity.sentence,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: SizedBox(
          height: 430,
          width: double.infinity,
          child: Stack(
            fit: StackFit.expand,
            children: [
              PtwMediaImage(image: activity.image),
              DecoratedBox(
                decoration: BoxDecoration(
                  gradient: PtwGradients.projectImageOverlay(primary),
                ),
              ),
              Padding(
                padding: EdgeInsets.fromLTRB(
                  first ? 72 : PtwSpacing.screenHorizontal,
                  first ? systemTop + PtwSpacing.sm : PtwSpacing.lg,
                  PtwSpacing.screenHorizontal,
                  PtwSpacing.lg,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(2),
                          decoration: const BoxDecoration(
                            color: PtwColors.textOnAccent,
                            shape: BoxShape.circle,
                          ),
                          child: ClipOval(
                            child: Image.asset(
                              activity.project.ownerAvatarAsset,
                              width: 38,
                              height: 38,
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                        const SizedBox(width: PtwSpacing.sm),
                        Expanded(
                          child: Text(
                            '@${activity.project.ownerHandle}',
                            style: PtwTypography.bodyStrong.copyWith(
                              color: PtwColors.textOnAccent,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const Spacer(),
                    Text(
                      activity.label,
                      style: PtwTypography.caption.copyWith(
                        color: PtwColors.textOnAccent,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.2,
                      ),
                    ),
                    const SizedBox(height: PtwSpacing.xs),
                    if (activity.type == PtwSocialActivityType.projectStarted)
                      SizedBox(
                        height: 112,
                        child: PtwStickerText.project(
                          activity.title,
                          compact: true,
                          alignment: Alignment.bottomLeft,
                        ),
                      )
                    else ...[
                      Text(
                        activity.title,
                        style: PtwTypography.titleLarge.copyWith(
                          color: PtwColors.textOnAccent,
                        ),
                      ),
                      const SizedBox(height: PtwSpacing.xs),
                      Text(
                        activity.evidence!.details,
                        style: PtwTypography.body.copyWith(
                          color: PtwColors.softWhite,
                        ),
                      ),
                    ],
                    const SizedBox(height: PtwSpacing.sm),
                    Text(
                      PtwFormatters.relative(activity.createdAt),
                      style: PtwTypography.bodyStrong.copyWith(
                        color: PtwColors.textOnAccent,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
