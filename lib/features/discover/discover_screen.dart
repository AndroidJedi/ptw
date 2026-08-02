import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/organisms/ptw_creator_shell.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class DiscoverScreen extends StatelessWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final projects = PtwScope.of(context).projects;
    return PtwCreatorShell(
      destination: PtwCreatorDestination.discover,
      child: SafeArea(
        child: CustomScrollView(
          key: const ValueKey(ComponentIds.discoverScreen),
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
              sliver: SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Who will prove it?', style: PtwTypography.display),
                    const SizedBox(height: PtwSpacing.xs),
                    Text(
                      'Pick a side. Say it straight.',
                      style: PtwTypography.body.copyWith(
                        color: PtwColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 120),
              sliver: SliverList.separated(
                key: const ValueKey(ComponentIds.discoverList),
                itemCount: projects.length,
                separatorBuilder:
                    (_, __) => const SizedBox(height: PtwSpacing.md),
                itemBuilder:
                    (context, index) => PtwProjectTile(
                      project: projects[index],
                      height: 250,
                      compact: true,
                      onTap: () => context.push('/p/${projects[index].id}'),
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
