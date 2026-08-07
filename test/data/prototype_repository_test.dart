import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/core/data/mock_json_loader.dart';
import 'package:ptw/core/data/ptw_prototype_repository.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/features/social_post_studio/ptw_story_composer.dart';
import 'package:ptw/models/ptw_evidence.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';
import 'package:ptw/models/ptw_project_draft.dart';
import 'package:ptw/models/ptw_prototype_snapshot.dart';
import 'package:ptw/models/ptw_response.dart';
import 'package:ptw/models/ptw_share_record.dart';
import 'package:ptw/models/ptw_social_activity.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

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

  test('v2 snapshots migrate as activated without losing project data', () {
    final migrated = PtwPrototypeSnapshot.fromJson({
      'schemaVersion': 2,
      'currentProjectByOwner': {'owner': 'project'},
      'projects': [
        {
          'id': 'project',
          'ownerId': 'owner',
          'ownerName': 'Owner',
          'ownerHandle': 'owner',
          'ownerAvatarAsset': 'avatar.jpg',
          'goal': 'Keep this goal',
          'deadline': '2026-12-31T00:00:00.000',
          'image': {'source': 'asset', 'path': 'project.jpg'},
          'primaryColor': 0xFFF4066E,
          'status': 'active',
          'createdAt': '2026-08-02T00:00:00.000',
        },
      ],
      'responses': <dynamic>[],
      'evidence': <dynamic>[],
    });

    expect(migrated.schemaVersion, PtwPrototypeSnapshot.currentSchemaVersion);
    expect(migrated.activatedAt, isNotNull);
    expect(migrated.projects.single.goal, 'Keep this goal');
    expect(migrated.draft, isNull);
    expect(migrated.shareRecords, isEmpty);
  });

  test('v3 legacy card records survive the v5 migration', () async {
    final seed = await const MockJsonLoader().load();
    final catalog = ShareCatalog.fromJson(
      jsonDecode(await rootBundle.loadString('assets/mock/share_content.json'))
          as Map<String, dynamic>,
    );
    final legacy = PtwShareRecord(
      id: 'legacy_share',
      projectId: catalog.scenarios.first.projectId,
      source: PtwShareSource.project,
      outcome: PtwShareOutcome.success,
      card: catalog.scenarios.first,
      format: ShareFormat.square,
      startedAt: DateTime(2026, 8, 2),
      completedAt: DateTime(2026, 8, 2, 0, 1),
    );
    final json =
        seed.snapshot.toJson()
          ..['schemaVersion'] = 3
          ..['shareRecords'] = [legacy.toJson()];

    final migrated = PtwPrototypeSnapshot.fromJson(json);

    expect(migrated.schemaVersion, PtwPrototypeSnapshot.currentSchemaVersion);
    expect(migrated.shareRecords.single.card, isNotNull);
    expect(migrated.shareRecords.single.story, isNull);
    expect(migrated.shareRecords.single.format, ShareFormat.square);
  });

  test('v4 fixed Story drafts migrate to generated layer values', () async {
    final seed = await const MockJsonLoader().load();
    final project = seed.snapshot.projects.first;
    final story = const PtwStoryComposer().create(
      project: project,
      event: ShareEvent.challengeCreated,
      now: DateTime(2026, 8, 2),
    );
    final draft = PtwProjectDraft(
      id: project.id,
      intent: PtwProjectDraftIntent.newChallenge,
      goal: project.goal,
      image: project.image,
      primaryColor: project.primaryColor,
      createdAt: project.createdAt,
      updatedAt: story.updatedAt,
      storyComposition: story,
    );
    final legacy =
        seed.snapshot.toJson()
          ..['schemaVersion'] = 4
          ..['draft'] = draft.toJson();

    final migrated = PtwPrototypeSnapshot.fromJson(legacy);
    final restored = migrated.draft!.storyComposition!;

    expect(restored.themeId, 'ptw_story_v1');
    expect(restored.editorValue, isNotNull);
    expect(
      restored.editorValue!['layerValues'],
      containsPair('headline', story.headline),
    );
    expect(restored.editorValue!['layerValues'], contains('secondary'));
    expect(restored.editorValue!['stickers'], hasLength(story.stickers.length));
  });

  test('proof activity falls back to its project image', () {
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
      createdAt: DateTime(2026, 8, 1),
    );
    final proof = PtwEvidence(
      id: 'proof',
      projectId: project.id,
      title: 'First result',
      details: 'It worked.',
      createdAt: DateTime(2026, 8, 2),
    );

    final activity = PtwSocialActivity.proofAdded(
      project: project,
      proof: proof,
    );

    expect(activity.image, same(project.image));
    expect(activity.title, proof.title);
  });
}
