import 'package:go_router/go_router.dart';

import '../features/discover/feed_screen.dart';
import '../features/evidence/add_evidence_screen.dart';
import '../features/inbox/inbox_screen.dart';
import '../features/participant/create_post_screen.dart';
import '../features/participant/creator_entry_screen.dart';
import '../features/participant/participant_home_screen.dart';
import '../features/story/guest_story_screen.dart';
import '../features/story/share_story_preview_screen.dart';
import '../features/share/share_models.dart';
import '../models/ptw_project_draft.dart';
import '../models/ptw_share_record.dart';
import '../state/ptw_app_state.dart';
import 'app_routes.dart';

abstract final class AppRouter {
  static GoRouter create({
    required PtwAppState state,
    String initialLocation = '/',
  }) => GoRouter(
    initialLocation: initialLocation,
    refreshListenable: state,
    redirect: (_, routeState) {
      if (!state.isReady || state.isActivated) return null;
      final path = routeState.uri.path;
      final protectedCreatorRoute =
          path == '/inbox' ||
          path == '/feed' ||
          path == '/projects/new' ||
          RegExp(r'^/projects/[^/]+/(share|proof/new)$').hasMatch(path) ||
          RegExp(r'^/projects/[^/]+$').hasMatch(path);
      return protectedCreatorRoute ? '/' : null;
    },
    routes: [
      GoRoute(
        path: '/',
        name: AppRoutes.entry,
        builder: (_, __) => const CreatorEntryScreen(),
      ),
      GoRoute(
        path: '/inbox',
        name: AppRoutes.inbox,
        builder: (_, __) => const InboxScreen(),
      ),
      GoRoute(
        path: '/feed',
        name: AppRoutes.feed,
        builder: (_, __) => const FeedScreen(),
      ),
      GoRoute(
        path: '/onboarding',
        name: AppRoutes.onboarding,
        builder:
            (_, __) => const CreatePostScreen(
              intent: PtwProjectDraftIntent.firstProject,
            ),
      ),
      GoRoute(
        path: '/share/draft',
        name: AppRoutes.shareDraft,
        builder:
            (_, routeState) => ShareStoryPreviewScreen.draft(
              source: _shareSource(
                routeState.uri.queryParameters['source'],
                fallback: PtwShareSource.onboarding,
              ),
            ),
      ),
      GoRoute(
        path: '/projects/new',
        name: AppRoutes.createProject,
        builder: (_, __) => const CreatePostScreen(),
      ),
      GoRoute(
        path: '/projects/:projectId',
        name: AppRoutes.project,
        builder:
            (_, routeState) => ParticipantHomeScreen(
              projectId: routeState.pathParameters['projectId']!,
              showActivatedMessage:
                  routeState.uri.queryParameters['activated'] == '1',
            ),
      ),
      GoRoute(
        path: '/projects/:projectId/share',
        name: AppRoutes.shareProject,
        builder: (_, state) {
          final event = ShareEvent.fromWire(state.uri.queryParameters['event']);
          return ShareStoryPreviewScreen.project(
            projectId: state.pathParameters['projectId']!,
            source: _shareSource(
              state.uri.queryParameters['source'],
              fallback: switch (event) {
                ShareEvent.milestoneReached => PtwShareSource.evidence,
                ShareEvent.newSkeptic ||
                ShareEvent.firstComment ||
                ShareEvent.topCommentChanged => PtwShareSource.inbox,
                _ => PtwShareSource.project,
              },
            ),
            event: event,
            momentId: state.uri.queryParameters['moment'],
          );
        },
      ),
      GoRoute(
        path: '/projects/:projectId/proof/new',
        name: AppRoutes.addEvidence,
        builder:
            (_, state) => AddEvidenceScreen(
              projectId: state.pathParameters['projectId']!,
            ),
      ),
      GoRoute(
        path: '/p/:projectId',
        name: AppRoutes.visitorProject,
        builder:
            (_, state) =>
                GuestStoryScreen(projectId: state.pathParameters['projectId']!),
        routes: [
          GoRoute(
            path: 'sent',
            name: AppRoutes.responseSent,
            builder:
                (_, state) => ResponseSentScreen(
                  projectId: state.pathParameters['projectId']!,
                ),
          ),
        ],
      ),
      GoRoute(
        path: '/:handle',
        name: AppRoutes.sharedHandle,
        builder:
            (_, state) =>
                SharedPromiseScreen(handle: state.pathParameters['handle']!),
      ),
    ],
  );
}

PtwShareSource _shareSource(
  String? value, {
  required PtwShareSource fallback,
}) =>
    PtwShareSource.values.where((item) => item.name == value).firstOrNull ??
    fallback;

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
