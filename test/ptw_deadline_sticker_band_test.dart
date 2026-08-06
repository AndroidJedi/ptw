import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/ui_kit/atoms/ptw_finish_flag_icon.dart';
import 'package:ptw/ui_kit/atoms/ptw_sticker_text.dart';
import 'package:ptw/ui_kit/organisms/ptw_deadline_sticker_band.dart';

void main() {
  testWidgets('rotated PTW sticker sits beside a plain deadline countdown', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PtwDeadlineStickerBand(daysRemaining: 45)),
      ),
    );

    expect(find.text('PTW'), findsOneWidget);
    expect(find.text('45'), findsOneWidget);
    expect(find.text('DAYS LEFT'), findsOneWidget);
    expect(find.byType(PtwFinishFlagIcon), findsOneWidget);
    final sticker = find.byKey(
      const ValueKey(ComponentIds.projectDeadlineSticker),
    );
    expect(sticker, findsOneWidget);
    final rotation = tester.widget<Transform>(
      find.ancestor(of: sticker, matching: find.byType(Transform)).first,
    );
    expect(rotation.transform.entry(0, 1), isNot(0));
    expect(
      find.descendant(of: sticker, matching: find.byType(PtwStickerText)),
      findsOneWidget,
    );
    expect(find.bySemanticsLabel('PTW. 45 days left'), findsOneWidget);
    semantics.dispose();
  });

  testWidgets('countdown uses a compact today state', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PtwDeadlineStickerBand(daysRemaining: 0)),
      ),
    );

    expect(find.text('TODAY'), findsOneWidget);
    expect(find.text('DAYS LEFT'), findsNothing);
  });
}
