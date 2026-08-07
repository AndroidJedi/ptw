import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/constants/component_ids.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';

import '../test_harness.dart';

final class _CorruptRepository implements PtwPrototypeRepository {
  bool corrupt = true;
  PtwPrototypeSnapshot? snapshot;

  @override
  Future<PtwPrototypeSnapshot?> load() async {
    if (corrupt) throw const FormatException('broken fixture');
    return snapshot;
  }

  @override
  Future<void> reset() async {
    corrupt = false;
    snapshot = null;
  }

  @override
  Future<void> save(PtwPrototypeSnapshot value) async => snapshot = value;
}

void main() {
  testWidgets('corrupt local data exposes a recoverable reset', (tester) async {
    await pumpPtw(tester, repository: _CorruptRepository());
    expect(find.text('Reset local prototype'), findsOneWidget);
    await tester.tap(find.text('Reset local prototype'));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey(ComponentIds.createProjectScreen)),
      findsOneWidget,
    );
  });
}
