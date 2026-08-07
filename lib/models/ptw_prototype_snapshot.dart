import 'ptw_evidence.dart';
import 'ptw_project.dart';
import 'ptw_project_draft.dart';
import 'ptw_response.dart';
import 'ptw_share_record.dart';

/// Versioned, database-like snapshot stored as one SharedPreferences JSON value.
final class PtwPrototypeSnapshot {
  const PtwPrototypeSnapshot({
    required this.schemaVersion,
    required this.currentProjectByOwner,
    required this.projects,
    required this.responses,
    required this.evidence,
    this.activatedAt,
    this.draft,
    this.shareRecords = const [],
  });

  static const currentSchemaVersion = 5;

  factory PtwPrototypeSnapshot.fromJson(Map<String, dynamic> json) {
    final version = json['schemaVersion'] as int;
    if (version != 2 &&
        version != 3 &&
        version != 4 &&
        version != currentSchemaVersion) {
      throw FormatException('Unsupported prototype schema: $version');
    }
    final projects =
        (json['projects'] as List<dynamic>)
            .cast<Map<String, dynamic>>()
            .map(PtwProject.fromJson)
            .toList();
    final currentProjectByOwner = Map<String, String>.from(
      json['currentProjectByOwner'] as Map<String, dynamic>,
    );
    return PtwPrototypeSnapshot(
      schemaVersion: currentSchemaVersion,
      currentProjectByOwner: currentProjectByOwner,
      projects: projects,
      responses:
          (json['responses'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map(PtwResponse.fromJson)
              .toList(),
      evidence:
          (json['evidence'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map(PtwEvidence.fromJson)
              .toList(),
      activatedAt:
          json['activatedAt'] == null
              ? version == 2 && currentProjectByOwner.isNotEmpty
                  ? (projects.isEmpty
                      ? DateTime.fromMillisecondsSinceEpoch(0)
                      : projects.first.createdAt)
                  : null
              : DateTime.parse(json['activatedAt'] as String),
      draft:
          json['draft'] == null
              ? null
              : PtwProjectDraft.fromJson(
                json['draft'] as Map<String, dynamic>,
                migrateStoryComposition: version < currentSchemaVersion,
              ),
      shareRecords:
          ((json['shareRecords'] as List<dynamic>?) ?? const [])
              .cast<Map<String, dynamic>>()
              .map(
                (item) => PtwShareRecord.fromJson(
                  item,
                  migrateStoryComposition: version < currentSchemaVersion,
                ),
              )
              .toList(),
    );
  }

  final int schemaVersion;
  final Map<String, String> currentProjectByOwner;
  final List<PtwProject> projects;
  final List<PtwResponse> responses;
  final List<PtwEvidence> evidence;
  final DateTime? activatedAt;
  final PtwProjectDraft? draft;
  final List<PtwShareRecord> shareRecords;

  PtwPrototypeSnapshot copyWith({
    Map<String, String>? currentProjectByOwner,
    List<PtwProject>? projects,
    List<PtwResponse>? responses,
    List<PtwEvidence>? evidence,
    DateTime? activatedAt,
    bool clearActivatedAt = false,
    PtwProjectDraft? draft,
    bool clearDraft = false,
    List<PtwShareRecord>? shareRecords,
  }) => PtwPrototypeSnapshot(
    schemaVersion: currentSchemaVersion,
    currentProjectByOwner: currentProjectByOwner ?? this.currentProjectByOwner,
    projects: projects ?? this.projects,
    responses: responses ?? this.responses,
    evidence: evidence ?? this.evidence,
    activatedAt: clearActivatedAt ? null : activatedAt ?? this.activatedAt,
    draft: clearDraft ? null : draft ?? this.draft,
    shareRecords: shareRecords ?? this.shareRecords,
  );

  Map<String, dynamic> toJson() => {
    'schemaVersion': schemaVersion,
    'currentProjectByOwner': currentProjectByOwner,
    'projects': projects.map((item) => item.toJson()).toList(),
    'responses': responses.map((item) => item.toJson()).toList(),
    'evidence': evidence.map((item) => item.toJson()).toList(),
    'activatedAt': activatedAt?.toIso8601String(),
    'draft': draft?.toJson(),
    'shareRecords': shareRecords.map((item) => item.toJson()).toList(),
  };
}
