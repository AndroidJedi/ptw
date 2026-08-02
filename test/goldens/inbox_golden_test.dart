import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';

import '../test_harness.dart';

void main() {
  testWidgets('inbox golden', (tester) async {
    await pumpPtw(tester, initialLocation: '/inbox');
    await expectLater(
      find.byType(PtwApp),
      matchesGoldenFile('../../goldens/v2_inbox.png'),
    );
  });
}
