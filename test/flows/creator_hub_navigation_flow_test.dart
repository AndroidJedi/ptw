import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/theme/ptw_colors.dart';

import '../test_harness.dart';

void main() {
  testWidgets('project hub opens immersive destinations with working back', (
    tester,
  ) async {
    await pumpPtw(tester);

    expect(find.text('Your project'), findsNothing);
    expect(find.text('PROVE THEM WRONG'), findsNothing);
    expect(
      find.byKey(const ValueKey(ComponentIds.projectInbox)),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey(ComponentIds.projectDiscover)),
      findsOneWidget,
    );
    final projectTile = tester.widget<Material>(
      find.byKey(const ValueKey(ComponentIds.projectTile)),
    );
    final projectShape = projectTile.shape! as RoundedRectangleBorder;
    expect(projectShape.side.color, PtwColors.textOnAccent);
    expect(projectShape.side.width, 1);

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

    await tester.tap(find.byKey(const ValueKey(ComponentIds.projectInbox)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.inboxScreen)),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey(ComponentIds.inboxBack)));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.projectHome)),
      findsOneWidget,
    );
  });
}
