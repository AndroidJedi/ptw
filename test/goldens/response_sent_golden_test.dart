import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/app/ptw_app.dart';

import '../test_harness.dart';

void main() {
  testWidgets('response sent golden', (tester) async {
    await pumpPtw(tester, initialLocation: '/p/challenge_red_friday/sent');
    await expectLater(
      find.byType(PtwApp),
      matchesGoldenFile('../../goldens/v2_response_sent.png'),
    );
  });
}
