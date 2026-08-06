import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/features/share/share_guide.dart';
import 'package:ptw/features/share/share_models.dart';

import 'share_test_data.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('every platform guide reaches its simulated composer', (
    tester,
  ) async {
    final catalog = ShareCatalog.fromJson(
      jsonDecode(await rootBundle.loadString('assets/mock/share_content.json'))
          as Map<String, dynamic>,
    );
    final png = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
    );

    for (final platform in SharePlatform.values) {
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder:
                (context) => TextButton(
                  onPressed:
                      () => showPtwShareGuide(
                        context: context,
                        asset: ShareAsset(
                          bytes: Uint8List.fromList(png),
                          format: platform.recommendedFormat,
                          fileName: 'card.png',
                        ),
                        card: sampleShareCard(ShareTemplateType.challenge),
                        guide: catalog.guide(platform),
                      ),
                  child: const Text('Open guide'),
                ),
          ),
        ),
      );
      await tester.tap(find.text('Open guide'));
      await tester.pumpAndSettle();

      final guide = catalog.guide(platform);
      for (var index = 1; index < guide.steps.length; index++) {
        final next = find.byKey(
          const ValueKey(ComponentIds.storyShareGuideNext),
        );
        await tester.ensureVisible(next);
        await tester.tap(next);
        await tester.pumpAndSettle();
      }
      final finish = find.byKey(
        const ValueKey(ComponentIds.storyShareGuideFinish),
      );
      await tester.ensureVisible(finish);
      await tester.tap(finish);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey(ComponentIds.storyViewer)),
        findsOneWidget,
        reason: platform.name,
      );
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();
    }
  });
}
