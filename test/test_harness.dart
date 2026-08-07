import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_media_service.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/features/share/share_service.dart';
import 'package:ptw/features/social_post_studio/ptw_story_composer.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_project_draft.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';
import 'package:ptw/models/ptw_share_record.dart';
import 'package:ptw/state/ptw_app_state.dart';

const testSurfaceSize = Size(393, 852);
final testNow = DateTime(2026, 8, 2, 12);
bool _testFontsLoaded = false;

final class FakePtwMediaService implements PtwMediaService {
  FakePtwMediaService({this.pickResult, this.recoveredResult, this.pickError});

  PtwImageRef? pickResult;
  PtwImageRef? recoveredResult;
  Object? pickError;
  int pickCount = 0;

  @override
  Future<void> initialize() async {}

  @override
  Future<PtwImageRef?> pickProjectImage() async {
    pickCount++;
    if (pickError != null) throw Exception(pickError);
    return pickResult;
  }

  @override
  Future<PtwImageRef?> recoverLostProjectImage() async => recoveredResult;

  @override
  String resolveFilePath(PtwImageRef image) => image.path;
}

final class FakePtwShareService implements PtwShareService {
  FakePtwShareService({
    this.result = const PtwShareResult(status: PtwShareResultStatus.success),
    this.error,
  });

  PtwShareResult result;
  Object? error;
  int shareCount = 0;
  ShareAsset? lastAsset;
  String? lastText;
  Rect? lastOrigin;

  @override
  Future<PtwShareResult> share({
    required ShareAsset asset,
    required String text,
    required Rect sharePositionOrigin,
  }) async {
    shareCount++;
    lastAsset = asset;
    lastText = text;
    lastOrigin = sharePositionOrigin;
    if (error != null) throw Exception(error);
    return result;
  }
}

final class PtwTestEnvironment {
  const PtwTestEnvironment({
    required this.repository,
    required this.media,
    required this.share,
  });

  final PtwPrototypeRepository repository;
  final FakePtwMediaService media;
  final FakePtwShareService share;
}

Future<PtwTestEnvironment> pumpPtw(
  WidgetTester tester, {
  String initialLocation = '/',
  PtwPrototypeRepository? repository,
  FakePtwMediaService? media,
  FakePtwShareService? share,
  bool activated = true,
}) async {
  final resolvedRepository =
      repository ??
      MemoryPrototypeRepository(
        initial: activated ? await _activatedSeedSnapshot() : null,
      );
  final resolvedMedia = media ?? FakePtwMediaService();
  final resolvedShare = share ?? FakePtwShareService();
  tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
    SystemChannels.platform,
    (_) async => null,
  );
  addTearDown(
    () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      null,
    ),
  );
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
  if (!_testFontsLoaded) {
    await _loadTestFonts();
    _testFontsLoaded = true;
  }
  await tester.binding.setSurfaceSize(testSurfaceSize);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    PtwApp(
      initialLocation: initialLocation,
      repository: resolvedRepository,
      mediaService: resolvedMedia,
      shareService: resolvedShare,
      now: () => testNow,
    ),
  );
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 100)),
  );
  for (var attempt = 0; attempt < 200; attempt++) {
    await tester.pump(const Duration(milliseconds: 50));
    final creatorReady =
        find
            .byKey(const ValueKey(ComponentIds.createProjectGoal))
            .evaluate()
            .isNotEmpty;
    final otherReady = [
      ComponentIds.projectHome,
      ComponentIds.visitorComposer,
      ComponentIds.inboxScreen,
      ComponentIds.feedScreen,
      ComponentIds.shareScreen,
      ComponentIds.responseSent,
    ].any((key) => find.byKey(ValueKey(key)).evaluate().isNotEmpty);
    if (creatorReady || otherReady) {
      break;
    }
  }
  final context = tester.element(find.byType(PtwApp));
  const photoAssets = [
    'assets/images/users/alex.jpg',
    'assets/images/users/maya.jpg',
    'assets/images/users/daniel.jpg',
    'assets/images/users/nina.jpg',
    'assets/images/users/jordan.jpg',
    'assets/images/users/chloe.jpg',
    'assets/images/users/marcus.jpg',
    'assets/images/users/elena.jpg',
    'assets/images/backgrounds/startup.jpg',
    'assets/images/backgrounds/fitness.jpg',
    'assets/images/backgrounds/business.jpg',
    'assets/images/backgrounds/technology.jpg',
    'assets/images/backgrounds/creative.jpg',
    'assets/images/backgrounds/education.jpg',
    'assets/images/backgrounds/career.jpg',
    'assets/images/backgrounds/travel.jpg',
  ];
  await tester.runAsync(
    () => Future.wait(
      photoAssets.map((asset) => precacheImage(AssetImage(asset), context)),
    ),
  );
  await tester.pump(const Duration(milliseconds: 100));
  return PtwTestEnvironment(
    repository: resolvedRepository,
    media: resolvedMedia,
    share: resolvedShare,
  );
}

Future<void> _loadTestFonts() {
  final textFonts =
      FontLoader('PtwRoboto')
        ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Medium.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf'));
  final stickerFonts = FontLoader('PtwLilitaOne')
    ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'));
  final iconFonts = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  return Future.wait([textFonts.load(), stickerFonts.load(), iconFonts.load()]);
}

Future<PtwPrototypeSnapshot> _activatedSeedSnapshot() async {
  final seed = await const MockJsonLoader().load();
  final current = Map<String, String>.from(seed.snapshot.currentProjectByOwner)
    ..[seed.currentUser.id] = seed.currentUser.initialProjectId;
  return seed.snapshot.copyWith(
    currentProjectByOwner: current,
    activatedAt: testNow.subtract(const Duration(days: 35)),
  );
}

Future<PtwProject> activateTestDraft(
  PtwAppState state, {
  required String goal,
  PtwProjectDraftIntent intent = PtwProjectDraftIntent.newChallenge,
  DateTime? deadline,
  PtwImageRef image = const PtwImageRef.asset(
    'assets/images/backgrounds/creative.jpg',
  ),
  int primaryColor = 0xFF7A32FF,
}) async {
  final initial = await state.ensureDraft(intent);
  final draft = await state.saveDraft(
    goal: goal,
    doubt: '',
    deadline: deadline,
    image: image,
    primaryColor: primaryColor,
    markPreviewGenerated: true,
  );
  final subject = PtwProject(
    id: draft.id,
    ownerId: state.currentUser.id,
    ownerName: state.currentUser.name,
    ownerHandle: state.currentUser.handle,
    ownerAvatarAsset: state.currentUser.avatarAsset,
    goal: draft.goal,
    deadline: draft.deadline,
    image: draft.image,
    primaryColor: draft.primaryColor,
    status: PtwProjectStatus.active,
    createdAt: initial.createdAt,
  );
  final story = const PtwStoryComposer().create(
    project: subject,
    event: ShareEvent.challengeCreated,
    now: state.now,
  );
  return (await state.completeStoryShare(
    composition: story,
    source:
        intent == PtwProjectDraftIntent.firstProject
            ? PtwShareSource.onboarding
            : PtwShareSource.newChallenge,
    outcome: PtwShareOutcome.success,
    startedAt: state.now,
  ))!;
}

Future<void> openStoryGuideAtFinalStep(WidgetTester tester) async {
  await openStoryShareStep(tester);
  await tester.ensureVisible(
    find.byKey(const ValueKey(ComponentIds.sharePrimary)),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const ValueKey(ComponentIds.sharePrimary)));
  await tester.pumpAndSettle();
  for (var step = 1; step < 4; step++) {
    await tester.tap(find.byKey(ValueKey('instagram_guide_next_$step')));
    await tester.pumpAndSettle();
  }
  expect(find.byKey(const ValueKey('instagram_guide_next_4')), findsOneWidget);
}

Future<void> openStoryShareStep(WidgetTester tester) async {
  final continueButton = find.byKey(const ValueKey(ComponentIds.storyContinue));
  if (continueButton.evaluate().isNotEmpty) {
    await tester.tap(continueButton);
    await tester.pumpAndSettle();
  }
  expect(
    find.byKey(const ValueKey(ComponentIds.shareCopyLink)),
    findsOneWidget,
  );
}

Future<void> submitFinalStoryShare(WidgetTester tester) async {
  await tester.tap(
    find.byKey(const ValueKey('instagram_guide_next_4')),
    warnIfMissed: false,
  );
  await tester.pump();
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 400)),
  );
  await tester.pumpAndSettle();
}
