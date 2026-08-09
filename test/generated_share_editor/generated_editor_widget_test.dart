import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const content = ShareEditorContent(
    projectId: 'project',
    headline: 'Build the thing',
    secondaryText: 'Think I won’t?',
    ownerName: 'Alex',
    ownerHandle: 'alex',
    avatar: ShareImageValue.asset('assets/images/users/alex.jpg'),
    cover: ShareImageValue.asset('assets/images/backgrounds/startup.jpg'),
    caption: 'Caption',
    publicLink: 'https://ptw.to/p/project',
  );

  testWidgets(
    'hidden tools are omitted and visible premium tools request upgrade',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(393, 852));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final source = (await ShareThemeBundle.loadAsset()).toJson();
      final toolbar =
          (source['toolbar'] as List<dynamic>).cast<Map<String, dynamic>>();
      toolbar.singleWhere((item) => item['id'] == 'looks')['access'] = {
        'mode': 'premiumVisible',
        'entitlementKey': 'premium_looks',
      };
      toolbar.singleWhere((item) => item['id'] == 'effects')['access'] = {
        'mode': 'premiumHidden',
        'entitlementKey': 'premium_effects',
      };
      final theme = ShareThemeConfig.fromJson(source);
      ShareLockedFeature? requested;

      await tester.pumpWidget(
        MaterialApp(
          home: GeneratedShareEditor(
            theme: theme,
            content: content,
            entitlements: (_) => false,
            onLockedFeatureTap: (feature) => requested = feature,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const ValueKey('story_tool_looks')), findsOneWidget);
      expect(find.byKey(const ValueKey('story_tool_effects')), findsNothing);
      await tester.tap(find.byKey(const ValueKey('story_tool_looks')));
      expect(requested?.entitlementKey, 'premium_looks');
    },
  );

  testWidgets('host registries render custom component types', (tester) async {
    final source = (await ShareThemeBundle.loadAsset()).toJson();
    final layers =
        (source['layers'] as List<dynamic>).cast<Map<String, dynamic>>();
    layers.singleWhere((item) => item['id'] == 'brand')['type'] = 'customBadge';
    final theme = ShareThemeConfig.fromJson(source);
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 360,
          height: 640,
          child: GeneratedShareRenderer(
            theme: theme,
            content: content,
            value: controller.value,
            registry: ShareComponentRegistry(
              builders: {
                'customBadge':
                    (_) => const ColoredBox(
                      key: ValueKey('custom_component'),
                      color: Colors.pink,
                    ),
              },
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byKey(const ValueKey('custom_component')), findsOneWidget);
  });

  testWidgets('renderer applies the configured post corner radius', (
    tester,
  ) async {
    final source = (await ShareThemeBundle.loadAsset()).toJson();
    (source['canvas'] as Map<String, dynamic>)['cornerRadius'] = 24;
    final theme = ShareThemeConfig.fromJson(source);
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 360,
          height: 640,
          child: GeneratedShareRenderer(
            theme: theme,
            content: content,
            value: controller.value,
          ),
        ),
      ),
    );
    await tester.pump();

    final clipFinder = find.byKey(
      const ValueKey('generated_share_canvas_clip'),
    );
    final clip = tester.widget<ClipRRect>(clipFinder);
    final radius = clip.borderRadius as BorderRadius;
    expect(radius.topLeft.x, 24 * tester.getSize(clipFinder).width / 360);
  });

  testWidgets('safe-zone guides are opt-in authoring overlays', (tester) async {
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 360,
          height: 640,
          child: GeneratedShareRenderer(
            theme: theme,
            content: content,
            value: controller.value,
            showAuthoringGuides: true,
          ),
        ),
      ),
    );
    await tester.pump();

    expect(
      find.byKey(const ValueKey('share_safe_zone_overlay')),
      findsOneWidget,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 360,
          height: 640,
          child: GeneratedShareRenderer(
            theme: theme,
            content: content,
            value: controller.value,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.byKey(const ValueKey('share_safe_zone_overlay')), findsNothing);
  });

  testWidgets(
    'photo and decoration pickers preserve purpose and support crop restoration',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(393, 852));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final theme = await ShareThemeBundle.loadAsset();
      final controller = ShareEditorController(theme: theme, content: content);
      addTearDown(controller.dispose);
      ShareImageRequest? lastRequest;

      await tester.pumpWidget(
        MaterialApp(
          home: GeneratedShareEditor(
            theme: theme,
            content: content,
            controller: controller,
            imagePicker: (request) async {
              lastRequest = request;
              return switch (request.purpose) {
                ShareImagePurpose.background => const ShareImageValue.asset(
                  'assets/images/backgrounds/creative.jpg',
                ),
                ShareImagePurpose.decoration => const ShareImageValue.asset(
                  'assets/images/decorations/candy_heart.png',
                ),
                ShareImagePurpose.layer => const ShareImageValue.asset(
                  'assets/images/users/maya.jpg',
                ),
              };
            },
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const ValueKey('story_tool_photo')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('story_replace_background')));
      await tester.pumpAndSettle();
      expect(lastRequest?.purpose, ShareImagePurpose.background);
      expect(
        controller.value.backgroundEdit.image?.path,
        'assets/images/backgrounds/creative.jpg',
      );
      await tester.tap(find.byKey(const ValueKey('story_use_project_photo')));
      await tester.pump();
      expect(controller.value.backgroundEdit.image, isNull);
      await tester.tap(find.byKey(const ValueKey('story_replace_background')));
      await tester.pumpAndSettle();

      final crop = tester.widget<GestureDetector>(
        find.byKey(const ValueKey('share_background_crop_surface')),
      );
      crop.onScaleStart!(ScaleStartDetails(focalPoint: Offset.zero));
      crop.onScaleUpdate!(
        ScaleUpdateDetails(
          focalPoint: Offset(20, 20),
          focalPointDelta: Offset(18, -12),
          scale: 1.5,
        ),
      );
      await tester.pump();
      expect(controller.value.backgroundEdit.zoom, 1.5);
      expect(controller.value.backgroundEdit.alignmentX, isNot(0));
      expect(controller.value.backgroundEdit.alignmentY, isNot(0));

      await tester.drag(
        find.byKey(const ValueKey('story_replace_background')),
        const Offset(-260, 0),
      );
      await tester.pump();
      final resetCrop = find.byKey(const ValueKey('story_reset_crop'));
      await tester.ensureVisible(resetCrop);
      await tester.pump();
      await tester.tap(resetCrop);
      await tester.pump();
      expect(controller.value.backgroundEdit.zoom, 1);
      expect(controller.value.backgroundEdit.alignmentX, 0);
      expect(controller.value.backgroundEdit.alignmentY, 0);

      await tester.tap(find.text('Avatar'));
      await tester.pumpAndSettle();
      expect(lastRequest?.purpose, ShareImagePurpose.layer);
      expect(lastRequest?.layerId, 'avatar');
      expect(
        (controller.layerValue('avatar') as ShareImageValue).path,
        'assets/images/users/maya.jpg',
      );

      await tester.tap(find.byKey(const ValueKey('story_tool_decor')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('story_upload_decoration')));
      await tester.pumpAndSettle();
      expect(lastRequest?.purpose, ShareImagePurpose.decoration);
      expect(controller.value.overlays, hasLength(1));
    },
  );

  testWidgets('text, filter, and texture controls update the shared renderer', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(393, 852));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final theme = await ShareThemeBundle.loadAsset();
    final controller = ShareEditorController(theme: theme, content: content);
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: GeneratedShareEditor(
          theme: theme,
          content: content,
          controller: controller,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('story_tool_text')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_headline_field')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_text_font')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('story_font_PtwPressStart2P')));
    await tester.pumpAndSettle();
    expect(
      controller.effectiveStyle('headline')['fontFamily'],
      'PtwPressStart2P',
    );

    await tester.tap(find.byKey(const ValueKey('story_text_color')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('story_fill_color_#FFF4066E')));
    await tester.pumpAndSettle();
    expect(controller.effectiveStyle('headline')['color'], '#FFF4066E');

    await tester.tap(find.byKey(const ValueKey('story_text_effect')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Hard offset'));
    await tester.pumpAndSettle();
    expect(controller.effectiveStyle('headline')['shadowX'], 3.0);
    expect(controller.effectiveStyle('headline')['shadowY'], 4.0);

    await tester.drag(
      find.byKey(const ValueKey('story_text_effect')),
      const Offset(-250, 0),
    );
    await tester.pump();
    final italic = find.byKey(const ValueKey('story_text_italic'));
    await tester.ensureVisible(italic);
    await tester.pump();
    await tester.tap(italic);
    await tester.pump();
    expect(controller.effectiveStyle('headline')['italic'], isTrue);

    await tester.tap(find.byKey(const ValueKey('story_tool_effects')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('story_filter_b&w')));
    await tester.pump();
    expect(controller.value.backgroundEdit.saturation, 0);
    await tester.tap(find.byKey(const ValueKey('story_texture_grain')));
    await tester.pump();
    expect(
      controller.value.backgroundEdit.texture,
      ShareBackgroundTexture.grain,
    );
    expect(
      find.byKey(const ValueKey('share_background_texture')),
      findsOneWidget,
    );
  });
}
