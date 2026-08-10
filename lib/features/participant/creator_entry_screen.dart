import 'package:flutter/material.dart';

import '../../models/ptw_share_record.dart';
import '../../state/ptw_app_state.dart';
import '../story/share_story_preview_screen.dart';

final class CreatorEntryScreen extends StatelessWidget {
  const CreatorEntryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    if (state.isActivated) {
      return ShareStoryPreviewScreen.project(
        projectId: state.currentProject.id,
        source: PtwShareSource.launch,
      );
    }
    final draft = state.draft;
    if (draft?.hasValidGoal == true) {
      return const ShareStoryPreviewScreen.draft(
        source: PtwShareSource.onboarding,
      );
    }
    return const Scaffold(
      body: Center(child: Text('Preparing your first Story…')),
    );
  }
}
