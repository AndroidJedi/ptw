import '../../models/ptw_evidence.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_response.dart';

final class PtwDemoActivity {
  const PtwDemoActivity({required this.responses, required this.evidence});

  final List<PtwResponse> responses;
  final List<PtwEvidence> evidence;
}

/// Creates project-scoped prototype activity with deterministic identities.
abstract final class PtwDemoActivityFactory {
  static PtwDemoActivity forProject({
    required PtwProject project,
    required DateTime referenceTime,
    required PtwImageRef proofImage,
  }) => PtwDemoActivity(
    evidence: [
      PtwEvidence(
        id: 'demo_proof_${project.id}_1',
        projectId: project.id,
        title: 'The first milestone is complete',
        details:
            'I finished the first concrete step and documented what changed.',
        createdAt: referenceTime.subtract(const Duration(minutes: 10)),
        media: proofImage,
      ),
      PtwEvidence(
        id: 'demo_proof_${project.id}_2',
        projectId: project.id,
        title: 'The next step is scheduled',
        details:
            'I committed to the next checkpoint and put it on the calendar.',
        createdAt: referenceTime.subtract(const Duration(hours: 2)),
      ),
    ],
    responses: [
      PtwResponse(
        id: 'demo_response_${project.id}_1',
        projectId: project.id,
        side: PtwResponseSide.believe,
        message:
            'This feels specific enough to follow. Keep showing the progress.',
        createdAt: referenceTime.subtract(const Duration(minutes: 25)),
      ),
      PtwResponse(
        id: 'demo_response_${project.id}_2',
        projectId: project.id,
        side: PtwResponseSide.doubt,
        message: 'What result will prove that this is actually working?',
        createdAt: referenceTime.subtract(const Duration(minutes: 47)),
      ),
      PtwResponse(
        id: 'demo_response_${project.id}_3',
        projectId: project.id,
        side: PtwResponseSide.believe,
        message: 'The deadline makes this feel real. I am watching.',
        createdAt: referenceTime.subtract(const Duration(hours: 4)),
      ),
      PtwResponse(
        id: 'demo_response_${project.id}_4',
        projectId: project.id,
        side: PtwResponseSide.doubt,
        message: 'What is the biggest thing that could stop you?',
        createdAt: referenceTime.subtract(const Duration(hours: 5)),
      ),
      PtwResponse(
        id: 'demo_response_${project.id}_5',
        projectId: project.id,
        side: PtwResponseSide.believe,
        message: 'I would share this with someone chasing the same goal.',
        createdAt: referenceTime.subtract(const Duration(days: 1)),
      ),
    ],
  );
}
