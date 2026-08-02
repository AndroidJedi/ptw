import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';

import '../test_harness.dart';

void main() {
  testWidgets('creator home golden', (tester) async {
    await pumpPtw(tester);
    await expectLater(
      find.byType(PtwApp),
      matchesGoldenFile('../../goldens/v2_creator_home.png'),
    );
  });
}
