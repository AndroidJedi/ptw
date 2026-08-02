import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/ptw_media_service.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_image_ref.dart';

const testSurfaceSize = Size(393, 852);
final testNow = DateTime(2026, 8, 2, 12);

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

final class PtwTestEnvironment {
  const PtwTestEnvironment({required this.repository, required this.media});

  final PtwPrototypeRepository repository;
  final FakePtwMediaService media;
}

Future<PtwTestEnvironment> pumpPtw(
  WidgetTester tester, {
  String initialLocation = '/',
  PtwPrototypeRepository? repository,
  FakePtwMediaService? media,
}) async {
  final resolvedRepository = repository ?? MemoryPrototypeRepository();
  final resolvedMedia = media ?? FakePtwMediaService();
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump();
  final textFonts =
      FontLoader('PtwRoboto')
        ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Medium.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf'));
  final stickerFonts = FontLoader('PtwLilitaOne')
    ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf'));
  final iconFonts = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  await Future.wait([textFonts.load(), stickerFonts.load(), iconFonts.load()]);
  await tester.binding.setSurfaceSize(testSurfaceSize);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    PtwApp(
      initialLocation: initialLocation,
      repository: resolvedRepository,
      mediaService: resolvedMedia,
      now: () => testNow,
    ),
  );
  const readyKeys = [
    ComponentIds.projectHome,
    ComponentIds.createProjectScreen,
    ComponentIds.visitorComposer,
    ComponentIds.inboxScreen,
    ComponentIds.feedScreen,
    ComponentIds.shareScreen,
    ComponentIds.responseSent,
  ];
  for (var attempt = 0; attempt < 60; attempt++) {
    await tester.pump(const Duration(milliseconds: 50));
    if (readyKeys.any(
      (key) => find.byKey(ValueKey(key)).evaluate().isNotEmpty,
    )) {
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
  );
}
