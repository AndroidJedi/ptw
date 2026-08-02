import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';

import '../test_harness.dart';

void main() {
  testWidgets('share project golden', (tester) async {
    await pumpPtw(
      tester,
      initialLocation: '/projects/challenge_red_friday/share',
    );
    await expectLater(
      find.byType(PtwApp),
      matchesGoldenFile('../../goldens/v2_share_project.png'),
    );
  });
}
