import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/social_post_studio/social_post_studio_app.dart';
import 'package:ptw/features/social_post_studio/social_post_studio_controller.dart';
import 'package:ptw/features/social_post_studio/story_post_card.dart';
import 'package:ptw/features/social_post_studio/studio_avatar_picker.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';

final class _FakeAvatarPicker implements StudioAvatarPicker {
  _FakeAvatarPicker({this.selection, this.error});

  final StudioAvatarSelection? selection;
  final Object? error;

  @override
  Future<StudioAvatarSelection?> pickAvatar() async {
    if (error != null) throw error!;
    return selection;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemeStickerCatalog catalog;

  setUpAll(() async {
    catalog = await loadMemeStickerCatalog();
    final fonts = <FontLoader>[
      FontLoader('PtwRoboto')
        ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'))
        ..addFont(rootBundle.load('assets/fonts/Roboto-Bold.ttf')),
      FontLoader('PtwLilitaOne')
        ..addFont(rootBundle.load('assets/fonts/LilitaOne-Regular.ttf')),
      FontLoader('MaterialIcons')
        ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')),
    ];
    await Future.wait(fonts.map((loader) => loader.load()));
  });

  Future<void> pumpStudio(
    WidgetTester tester, {
    Size size = const Size(1440, 900),
    StudioAvatarPicker? picker,
  }) async {
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      SocialPostStudioApp(catalog: catalog, avatarPicker: picker),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('edits card content and enforces the three-sticker limit', (
    tester,
  ) async {
    await pumpStudio(tester);

    await tester.enterText(
      find.byKey(const ValueKey('studio_message')),
      'make your doubt useful.',
    );
    await tester.tap(
      find.byKey(const ValueKey('studio_background_gradient_hot')),
    );
    await tester.tap(find.byKey(const ValueKey('studio_add_cheering_blob')));
    await tester.tap(find.byKey(const ValueKey('studio_add_victory_hand')));
    await tester.tap(find.byKey(const ValueKey('studio_add_turbo_rocket')));
    await tester.pump();

    expect(find.text('make your doubt useful.'), findsWidgets);
    expect(find.byKey(const ValueKey('studio_sticker_limit')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('studio_transform_handle')),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey('studio_layer_delete')));
    await tester.pump();
    expect(find.byKey(const ValueKey('studio_sticker_limit')), findsNothing);
  });

  testWidgets('transform handle changes the selected sticker', (tester) async {
    await tester.binding.setSurfaceSize(const Size(500, 720));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = SocialPostStudioController(catalog: catalog)
      ..addSticker('cheering_blob');
    addTearDown(controller.dispose);
    final before = controller.selectedPlacement!;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 360,
              height: 640,
              child: EditableStoryPostCard(controller: controller),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(
      find.byKey(const ValueKey('studio_transform_handle')),
      const Offset(35, 18),
    );
    await tester.pump();

    final after = controller.selectedPlacement!;
    expect(after.scale, isNot(before.scale));
    expect(after.rotation, isNot(before.rotation));

    await tester.tap(
      find.byKey(ValueKey('studio_canvas_sticker_${before.instanceId}')),
    );
    final beforeNudge = controller.selectedPlacement!.centerX;
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pump();
    expect(controller.selectedPlacement!.centerX, greaterThan(beforeNudge));
    await tester.sendKeyEvent(LogicalKeyboardKey.delete);
    await tester.pump();
    expect(controller.draft.stickers, isEmpty);
  });

  testWidgets('browser avatar success and failure are surfaced', (
    tester,
  ) async {
    final data = await rootBundle.load('assets/images/users/maya.jpg');
    await pumpStudio(
      tester,
      picker: _FakeAvatarPicker(
        selection: StudioAvatarSelection(
          bytes: data.buffer.asUint8List(),
          mimeType: 'image/jpeg',
        ),
      ),
    );
    await tester.tap(find.byKey(const ValueKey('studio_pick_avatar')));
    await tester.pumpAndSettle();
    expect(find.byType(Image), findsWidgets);

    await tester.pumpWidget(const SizedBox.shrink());
    await pumpStudio(
      tester,
      picker: _FakeAvatarPicker(
        error: const StudioAvatarPickException('Choose a smaller image.'),
      ),
    );
    await tester.tap(find.byKey(const ValueKey('studio_pick_avatar')));
    await tester.pumpAndSettle();
    expect(find.text('Choose a smaller image.'), findsOneWidget);
  });

  testWidgets('desktop and narrow layouts render without overflow', (
    tester,
  ) async {
    await pumpStudio(tester);
    expect(tester.takeException(), isNull);

    await tester.binding.setSurfaceSize(const Size(390, 844));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('social_post_studio_screen')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}
