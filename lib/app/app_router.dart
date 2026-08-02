import 'package:go_router/go_router.dart';

import '../features/discover/feed_screen.dart';
import '../features/evidence/add_evidence_screen.dart';
import '../features/inbox/inbox_screen.dart';
import '../features/participant/create_post_screen.dart';
import '../features/participant/participant_home_screen.dart';
import '../features/story/guest_story_screen.dart';
import '../features/story/share_story_preview_screen.dart';
import 'app_routes.dart';

abstract final class AppRouter {
  static GoRouter create({String initialLocation = '/'}) => GoRouter(
    initialLocation: initialLocation,
    routes: [
      GoRoute(
        path: '/',
        name: AppRoutes.project,
        builder: (_, __) => const ParticipantHomeScreen(),
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
        path: '/projects/new',
        name: AppRoutes.createProject,
        builder: (_, __) => const CreatePostScreen(),
      ),
      GoRoute(
        path: '/projects/:projectId/share',
        name: AppRoutes.shareProject,
        builder:
            (_, state) => ShareStoryPreviewScreen(
              projectId: state.pathParameters['projectId']!,
            ),
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
