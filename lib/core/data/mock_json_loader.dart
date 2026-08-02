import 'dart:convert';

import 'package:flutter/services.dart';

import '../../models/ptw_evidence.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_post_background.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_prototype_snapshot.dart';
import '../../models/ptw_response.dart';
import '../../models/ptw_user.dart';

final class PtwSeedData {
  const PtwSeedData({
    required this.currentUser,
    required this.curatedImages,
    required this.snapshot,
  });

  final PtwUser currentUser;
  final List<PtwPostBackground> curatedImages;
  final PtwPrototypeSnapshot snapshot;
}

/// Converts the bundled legacy mock fixtures into the focused v2 domain.
final class MockJsonLoader {
  const MockJsonLoader();

  static final _prototypeToday = DateTime(2026, 8, 2);
  static final _prototypeActivityTime = DateTime(2026, 8, 2, 12);

  Future<PtwSeedData> load() async {
    final values = await Future.wait([
      rootBundle.loadString('assets/mock/current_user.json'),
      rootBundle.loadString('assets/mock/users.json'),
      rootBundle.loadString('assets/mock/challenges.json'),
      rootBundle.loadString('assets/mock/evidence.json'),
      rootBundle.loadString('assets/mock/backgrounds.json'),
      rootBundle.loadString('assets/mock/comments.json'),
    ]);
    final currentUser = PtwUser.fromJson(_object(values[0]));
    final users = _list(values[1]).map(PtwUser.fromJson).toList();
    final usersById = {for (final user in users) user.id: user};
    final challengeRows = _list(values[2]);
    final projects = <PtwProject>[];
    for (var index = 0; index < challengeRows.length; index++) {
      final row = challengeRows[index];
      final owner = usersById[row['ownerId'] as String]!;
      final completed = row['status'] == 'completed';
      projects.add(
        PtwProject(
          id: row['id'] as String,
          ownerId: owner.id,
          ownerName: owner.name,
          ownerHandle: owner.handle,
          ownerAvatarAsset: owner.avatarAsset,
          goal: row['title'] as String,
          deadline:
              completed
                  ? DateTime(2026, 7, 18)
                  : _prototypeToday.add(
                    Duration(days: row['daysRemaining'] as int),
                  ),
          image: PtwImageRef.asset(row['backgroundAsset'] as String),
          primaryColor: _colorFor(row['category'] as String),
          status:
              completed ? PtwProjectStatus.completed : PtwProjectStatus.active,
          createdAt: _prototypeToday.subtract(Duration(days: 35 + index * 4)),
        ),
      );
    }

    final evidenceRows = _list(values[3]);
    final evidence = <PtwEvidence>[];
    for (var index = 0; index < evidenceRows.length; index++) {
      final row = evidenceRows[index];
      evidence.add(
        PtwEvidence(
          id: row['id'] as String,
          projectId: row['challengeId'] as String,
          title: row['title'] as String,
          details: row['details'] as String,
          createdAt: switch (row['id']) {
            'evidence_001' => _prototypeActivityTime.subtract(
              const Duration(minutes: 10),
            ),
            'evidence_002' => _prototypeActivityTime.subtract(
              const Duration(hours: 2),
            ),
            _ => _prototypeToday.subtract(Duration(days: index + 1)),
          },
          media:
              row['mediaAsset'] == null
                  ? null
                  : PtwImageRef.asset(row['mediaAsset'] as String),
        ),
      );
    }

    final commentRows = _list(values[5]);
    final responses = <PtwResponse>[];
    for (var index = 0; index < commentRows.length; index++) {
      final row = commentRows[index];
      final createdAt = switch (index) {
        0 => _prototypeActivityTime.subtract(const Duration(minutes: 25)),
        1 => _prototypeActivityTime.subtract(const Duration(minutes: 47)),
        2 => _prototypeActivityTime.subtract(const Duration(hours: 4)),
        _ => _prototypeToday.subtract(Duration(hours: index + 1)),
      };
      responses.add(
        PtwResponse(
          id: 'seed_response_${index + 1}',
          projectId: row['challengeId'] as String,
          side:
              row['sentiment'] == 'doubt'
                  ? PtwResponseSide.doubt
                  : PtwResponseSide.believe,
          message: row['body'] as String,
          createdAt: createdAt,
          readAt: index < 2 ? createdAt.add(const Duration(minutes: 8)) : null,
        ),
      );
    }

    return PtwSeedData(
      currentUser: currentUser,
      curatedImages: _list(values[4]).map(PtwPostBackground.fromJson).toList(),
      snapshot: PtwPrototypeSnapshot(
        schemaVersion: PtwPrototypeSnapshot.currentSchemaVersion,
        currentProjectByOwner: {
          for (final user in users) user.id: user.initialProjectId,
        },
        projects: projects,
        responses: responses,
        evidence: evidence,
      ),
    );
  }

  static int _colorFor(String category) => switch (category) {
    'fitness' => 0xFFFF4D2E,
    'business' => 0xFFFF8A00,
    'technology' => 0xFF315CFF,
    'creative' => 0xFFF4066E,
    'education' => 0xFF7A32FF,
    'career' => 0xFF00A39A,
    'travel' => 0xFFFF4D2E,
    _ => 0xFFF4066E,
  };

  Map<String, dynamic> _object(String value) =>
      jsonDecode(value) as Map<String, dynamic>;

  List<Map<String, dynamic>> _list(String value) =>
      (jsonDecode(value) as List<dynamic>).cast<Map<String, dynamic>>();
}
