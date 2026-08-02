import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../state/ptw_app_state.dart';

enum PtwCreatorDestination { project, inbox, discover }

final class PtwCreatorShell extends StatelessWidget {
  const PtwCreatorShell({
    required this.destination,
    required this.child,
    super.key,
  });

  final PtwCreatorDestination destination;
  final Widget child;

  @override
  Widget build(BuildContext context) => Scaffold(
    key: const ValueKey(ComponentIds.creatorShell),
    extendBody: true,
    body: child,
    bottomNavigationBar: SafeArea(
      minimum: const EdgeInsets.fromLTRB(28, 0, 28, 12),
      child: Container(
        height: 66,
        padding: const EdgeInsets.all(7),
        decoration: BoxDecoration(
          color: PtwColors.ink,
          borderRadius: BorderRadius.circular(PtwRadius.pill),
          boxShadow: [
            BoxShadow(
              color: PtwColors.ink.withValues(alpha: 0.28),
              blurRadius: 24,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Row(
          children: [
            _NavItem(
              key: const ValueKey(ComponentIds.creatorProjectNav),
              selected: destination == PtwCreatorDestination.project,
              icon: Icons.bolt_rounded,
              label: 'Project',
              onTap: () => context.go('/'),
            ),
            _NavItem(
              key: const ValueKey(ComponentIds.creatorInboxNav),
              selected: destination == PtwCreatorDestination.inbox,
              icon: Icons.inbox_rounded,
              label: 'Inbox',
              badge: PtwScope.of(context).unreadResponseCount,
              onTap: () => context.go('/inbox'),
            ),
            _NavItem(
              key: const ValueKey(ComponentIds.creatorDiscoverNav),
              selected: destination == PtwCreatorDestination.discover,
              icon: Icons.explore_rounded,
              label: 'Discover',
              onTap: () => context.go('/discover'),
            ),
          ],
        ),
      ),
    ),
  );
}

final class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.selected,
    required this.icon,
    required this.label,
    required this.onTap,
    super.key,
    this.badge = 0,
  });

  final bool selected;
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final int badge;

  @override
  Widget build(BuildContext context) => Expanded(
    child: InkWell(
      borderRadius: BorderRadius.circular(PtwRadius.pill),
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: selected ? PtwColors.surfacePrimary : PtwColors.transparent,
          borderRadius: BorderRadius.circular(PtwRadius.pill),
        ),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    icon,
                    color: selected ? PtwColors.ink : PtwColors.textOnAccent,
                    size: 20,
                  ),
                  if (selected) ...[
                    const SizedBox(width: PtwSpacing.xxs),
                    Text(
                      label,
                      style: PtwTypography.caption.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (badge > 0)
              Positioned(
                right: selected ? 4 : 18,
                top: 1,
                child: Container(
                  constraints: const BoxConstraints(
                    minWidth: 18,
                    minHeight: 18,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(
                    color: PtwColors.hotPink,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '$badge',
                    style: PtwTypography.caption.copyWith(
                      color: PtwColors.textOnAccent,
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    ),
  );
}
