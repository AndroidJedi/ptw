import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share_theme_builder/share_theme_builder_app.dart';
import 'package:ptw/features/share_theme_builder/theme_builder_controller.dart';
import 'package:ptw/generated_share_editor/generated_share_editor.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('desktop builder exposes panes, premium preview, and nudging', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ThemeBuilderController(
      await ShareThemeBundle.loadAsset(),
    )..selectLayer('headline');
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(useMaterial3: true),
        home: ShareThemeBuilderScreen(controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('LOOKS'), findsOneWidget);
    expect(find.text('LAYERS'), findsOneWidget);
    expect(find.text('INSPECTOR'), findsOneWidget);
    expect(find.byKey(const ValueKey('builder_generate_zip')), findsOneWidget);

    final before = controller.editingLayer!.transform.x;
    await tester.tap(
      find.byKey(const ValueKey('builder_canvas_layer_headline')),
    );
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pump();
    expect(controller.editingLayer!.transform.x, before + 1);

    await tester.tap(find.text('Premium').first);
    await tester.pump();
    expect(controller.previewPremium, isTrue);
  });
}
