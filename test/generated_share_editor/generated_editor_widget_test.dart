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
      toolbar.singleWhere((item) => item['id'] == 'backgrounds')['access'] = {
        'mode': 'premiumHidden',
        'entitlementKey': 'premium_backgrounds',
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
      expect(
        find.byKey(const ValueKey('story_tool_backgrounds')),
        findsNothing,
      );
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
}
