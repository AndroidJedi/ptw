import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class DiscoverScreen extends StatelessWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final projects = PtwScope.of(context).projects;
    final systemPadding = MediaQuery.paddingOf(context);
    final systemTop = systemPadding.top;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.discoverScreen),
      safeArea: false,
      child: Stack(
        children: [
          ListView.separated(
            key: const ValueKey(ComponentIds.discoverList),
            padding: EdgeInsets.fromLTRB(
              PtwSpacing.screenHorizontal,
              systemTop + PtwSpacing.xxxl + PtwSpacing.sm,
              PtwSpacing.screenHorizontal,
              systemPadding.bottom + PtwSpacing.md,
            ),
            itemCount: projects.length,
            separatorBuilder: (_, __) => const SizedBox(height: PtwSpacing.md),
            itemBuilder:
                (context, index) => PtwProjectTile(
                  project: projects[index],
                  height: 280,
                  compact: true,
                  onTap: () => context.push('/p/${projects[index].id}'),
                ),
          ),
          Positioned(
            left: PtwSpacing.xs,
            top: systemTop + PtwSpacing.xxs,
            child: const PtwBackButton(
              key: ValueKey(ComponentIds.discoverBack),
              fallbackRoute: '/',
            ),
          ),
        ],
      ),
    );
  }
}
