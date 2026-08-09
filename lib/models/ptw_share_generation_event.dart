enum ShareGenerationEventType {
  generationStarted,
  stateConfirmed,
  candidatesShown,
  candidateSelected,
  optionsRegenerated,
  headlineEdited,
  photoChanged,
  exportCompleted,
  shareInvoked,
}

/// Vendor-neutral, media-free instrumentation for the local v1 prototype.
final class ShareGenerationEvent {
  const ShareGenerationEvent({
    required this.id,
    required this.sessionId,
    required this.projectId,
    required this.type,
    required this.timestamp,
    this.candidateId,
    this.journeyState,
    this.elapsedMilliseconds,
  });

  factory ShareGenerationEvent.fromJson(Map<String, dynamic> json) =>
      ShareGenerationEvent(
        id: json['id'] as String,
        sessionId: json['sessionId'] as String,
        projectId: json['projectId'] as String,
        type: ShareGenerationEventType.values.byName(json['type'] as String),
        timestamp: DateTime.parse(json['timestamp'] as String),
        candidateId: json['candidateId'] as String?,
        journeyState: json['journeyState'] as String?,
        elapsedMilliseconds: json['elapsedMilliseconds'] as int?,
      );

  final String id;
  final String sessionId;
  final String projectId;
  final ShareGenerationEventType type;
  final DateTime timestamp;
  final String? candidateId;
  final String? journeyState;
  final int? elapsedMilliseconds;

  Map<String, dynamic> toJson() => {
    'id': id,
    'sessionId': sessionId,
    'projectId': projectId,
    'type': type.name,
    'timestamp': timestamp.toIso8601String(),
    'candidateId': candidateId,
    'journeyState': journeyState,
    'elapsedMilliseconds': elapsedMilliseconds,
  };
}
