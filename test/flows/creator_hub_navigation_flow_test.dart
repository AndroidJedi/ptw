import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/theme/ptw_colors.dart';
import 'package:ptw/ui_kit/atoms/ptw_black_button.dart';
import 'package:ptw/ui_kit/atoms/ptw_sticker_text.dart';

import '../test_harness.dart';

void main() {
  testWidgets('project hub opens immersive destinations with working back', (
    tester,
  ) async {
    await pumpPtw(tester);

    expect(find.text('Your project'), findsNothing);
    expect(find.text('PROVE THEM WRONG'), findsNothing);
    expect(find.byKey(const ValueKey(ComponentIds.projectInbox)), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.projectDiscover)),
      findsNothing,
    );
    expect(find.byType(PtwBlackButton), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey(ComponentIds.projectShare)),
        matching: find.byType(PtwStickerText),
      ),
      findsOneWidget,
    );
    final projectTile = tester.widget<Material>(
      find.byKey(const ValueKey(ComponentIds.projectTile)),
    );
    final projectShape = projectTile.shape! as RoundedRectangleBorder;
    expect(projectShape.side.color, PtwColors.textOnAccent);
    expect(projectShape.side.width, 1);

    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectShare)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.actionSheet)),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey(ComponentIds.projectActionShare)),
        matching: find.byType(PtwStickerText),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const ValueKey(ComponentIds.projectInbox)),
        matching: find.byType(PtwStickerText),
      ),
      findsNothing,
    );
    expect(find.text('Inbox · 1 unread'), findsOneWidget);

    await tester.tapAt(const Offset(8, 8));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey(ComponentIds.actionSheet)), findsNothing);

    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectShare)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectDiscover)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.discoverScreen)),
      findsOneWidget,
    );
    expect(find.text('Who will prove it?'), findsNothing);
    final discoverTiles = find.byKey(const ValueKey(ComponentIds.projectTile));
    expect(
      tester.getSize(discoverTiles.at(0)).height,
      tester.getSize(discoverTiles.at(1)).height,
    );

    await tester.tap(
      find.byKey(const ValueKey(ComponentIds.projectTile)).first,
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.visitorComposer)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.visitorBack)),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.visitorBack)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey(ComponentIds.discoverBack)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectShare)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectInbox)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.inboxScreen)),
      findsOneWidget,
    );
    expect(find.byType(PtwBlackButton), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey(ComponentIds.inboxBack)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );
  });
}
