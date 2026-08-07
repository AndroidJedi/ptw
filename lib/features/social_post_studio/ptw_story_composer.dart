import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_story_composition.dart';
import '../share/share_models.dart';
import 'story_look_presets.dart';

final class PtwStoryComposer {
  const PtwStoryComposer();

  PtwStoryComposition create({
    required PtwProject project,
    required ShareEvent event,
    required DateTime now,
    String? momentId,
  }) {
    final headline = project.goal.trim();
    final dare = dareFor(event);
    final base = PtwStoryComposition(
      projectId: project.id,
      eventName: event.name,
      momentId: momentId,
      headline: headline,
      dare: dare,
      avatar: PtwImageRef.asset(project.ownerAvatarAsset),
      projectBackground: project.image,
      lookId: PtwStoryLooks.all.first.id,
      textTreatment: PtwStoryTextTreatment.clean,
      stickers: const [],
      caption: '$headline\n$dare',
      createdAt: now,
      updatedAt: now,
    );
    final seed = '${project.id}:${momentId ?? event.name}';
    return PtwStoryLooks.apply(
      base,
      PtwStoryLooks.all[PtwStoryLooks.indexForSeed(seed)],
      now,
    );
  }

  String dareFor(ShareEvent event) => switch (event) {
    ShareEvent.milestoneReached => 'Still doubting?',
    ShareEvent.newSkeptic ||
    ShareEvent.firstComment ||
    ShareEvent.topCommentChanged => 'They said I won’t. Agree?',
    ShareEvent.newSupporter ||
    ShareEvent.weeklyProgress => 'They believe. Do you?',
    ShareEvent.goalCompleted => 'I did it. What now?',
    _ => 'Think I won’t?',
  };
}
