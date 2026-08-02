import 'ptw_evidence.dart';
import 'ptw_image_ref.dart';
import 'ptw_project.dart';

enum PtwSocialActivityType { projectStarted, proofAdded }

/// A derived social event. It is never serialized into the prototype snapshot.
final class PtwSocialActivity {
  PtwSocialActivity.projectStarted({required this.project})
    : id = 'activity_project_${project.id}',
      type = PtwSocialActivityType.projectStarted,
      evidence = null,
      createdAt = project.createdAt;

  PtwSocialActivity.proofAdded({
    required this.project,
    required PtwEvidence proof,
  }) : id = 'activity_proof_${proof.id}',
       type = PtwSocialActivityType.proofAdded,
       evidence = proof,
       createdAt = proof.createdAt;

  final String id;
  final PtwSocialActivityType type;
  final PtwProject project;
  final PtwEvidence? evidence;
  final DateTime createdAt;

  PtwImageRef get image => evidence?.media ?? project.image;

  String get label => switch (type) {
    PtwSocialActivityType.projectStarted => 'STARTED A PROJECT',
    PtwSocialActivityType.proofAdded => 'POSTED PROOF',
  };

  String get title => evidence?.title ?? project.goal;

  String get sentence => switch (type) {
    PtwSocialActivityType.projectStarted =>
      '@${project.ownerHandle} started “${project.goal}”',
    PtwSocialActivityType.proofAdded =>
      '@${project.ownerHandle} proved “${evidence!.title}”',
  };
}
