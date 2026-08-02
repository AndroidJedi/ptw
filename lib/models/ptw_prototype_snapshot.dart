import 'ptw_evidence.dart';
import 'ptw_project.dart';
import 'ptw_response.dart';

/// Versioned, database-like snapshot stored as one SharedPreferences JSON value.
final class PtwPrototypeSnapshot {
  const PtwPrototypeSnapshot({
    required this.schemaVersion,
    required this.currentProjectByOwner,
    required this.projects,
    required this.responses,
    required this.evidence,
  });

  static const currentSchemaVersion = 2;

  factory PtwPrototypeSnapshot.fromJson(Map<String, dynamic> json) {
    final version = json['schemaVersion'] as int;
    if (version != currentSchemaVersion) {
      throw FormatException('Unsupported prototype schema: $version');
    }
    return PtwPrototypeSnapshot(
      schemaVersion: version,
      currentProjectByOwner: Map<String, String>.from(
        json['currentProjectByOwner'] as Map<String, dynamic>,
      ),
      projects:
          (json['projects'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map(PtwProject.fromJson)
              .toList(),
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
    );
  }

  final int schemaVersion;
  final Map<String, String> currentProjectByOwner;
  final List<PtwProject> projects;
  final List<PtwResponse> responses;
  final List<PtwEvidence> evidence;

  PtwPrototypeSnapshot copyWith({
    Map<String, String>? currentProjectByOwner,
    List<PtwProject>? projects,
    List<PtwResponse>? responses,
    List<PtwEvidence>? evidence,
  }) => PtwPrototypeSnapshot(
    schemaVersion: currentSchemaVersion,
    currentProjectByOwner: currentProjectByOwner ?? this.currentProjectByOwner,
    projects: projects ?? this.projects,
    responses: responses ?? this.responses,
    evidence: evidence ?? this.evidence,
  );

  Map<String, dynamic> toJson() => {
    'schemaVersion': schemaVersion,
    'currentProjectByOwner': currentProjectByOwner,
    'projects': projects.map((item) => item.toJson()).toList(),
    'responses': responses.map((item) => item.toJson()).toList(),
    'evidence': evidence.map((item) => item.toJson()).toList(),
  };
}
