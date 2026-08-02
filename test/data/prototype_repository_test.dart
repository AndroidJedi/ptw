import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';
import 'package:ptw/models/ptw_response.dart';

void main() {
  test('snapshot round-trips through repository and reset clears it', () async {
    final project = PtwProject(
      id: 'project',
      ownerId: 'owner',
      ownerName: 'Owner',
      ownerHandle: 'owner',
      ownerAvatarAsset: 'avatar.jpg',
      goal: 'Finish the prototype',
      deadline: DateTime(2026, 12, 31),
      image: const PtwImageRef.asset('project.jpg'),
      primaryColor: 0xFFF4066E,
      status: PtwProjectStatus.active,
      createdAt: DateTime(2026, 8, 2),
    );
    final snapshot = PtwPrototypeSnapshot(
      schemaVersion: PtwPrototypeSnapshot.currentSchemaVersion,
      currentProjectByOwner: const {'owner': 'project'},
      projects: [project],
      responses: [
        PtwResponse(
          id: 'response',
          projectId: 'project',
          side: PtwResponseSide.doubt,
          message: 'Prove it.',
          createdAt: DateTime(2026, 8, 2),
        ),
      ],
      evidence: const [],
    );
    final repository = MemoryPrototypeRepository();
    expect(await repository.load(), isNull);
    await repository.save(snapshot);
    final restored = await repository.load();
    expect(restored!.projects.single.goal, 'Finish the prototype');
    expect(restored.responses.single.side, PtwResponseSide.doubt);
    await repository.reset();
    expect(await repository.load(), isNull);
  });

  test('unsupported snapshots are rejected', () {
    expect(
      () => PtwPrototypeSnapshot.fromJson({
        'schemaVersion': 99,
        'currentProjectByOwner': <String, dynamic>{},
        'projects': <dynamic>[],
        'responses': <dynamic>[],
        'evidence': <dynamic>[],
      }),
      throwsFormatException,
    );
  });
}
