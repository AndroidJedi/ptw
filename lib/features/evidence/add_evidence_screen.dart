import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_image_ref.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';

final class AddEvidenceScreen extends StatefulWidget {
  const AddEvidenceScreen({required this.projectId, super.key});

  final String projectId;

  @override
  State<AddEvidenceScreen> createState() => _AddEvidenceScreenState();
}

final class _AddEvidenceScreenState extends State<AddEvidenceScreen> {
  final _titleController = TextEditingController();
  final _detailsController = TextEditingController();
  PtwImageRef? _media;
  bool _saving = false;

  @override
  void dispose() {
    _titleController.dispose();
    _detailsController.dispose();
    super.dispose();
  }

  Future<void> _pick(PtwAppState state) async {
    try {
      final result = await state.mediaService.pickProjectImage();
      if (result != null && mounted) setState(() => _media = result);
    } on Exception {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('That photo could not be imported.')),
        );
      }
    }
  }

  Future<void> _publish(PtwAppState state) async {
    if (_titleController.text.trim().isEmpty ||
        _detailsController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add the result and why it matters.')),
      );
      return;
    }
    setState(() => _saving = true);
    try {
      await state.addEvidence(
        projectId: widget.projectId,
        title: _titleController.text,
        details: _detailsController.text,
        media: _media,
      );
      if (mounted) context.pop();
    } on Exception {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Proof could not be saved.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    final project = state.maybeProjectById(widget.projectId);
    if (project == null) {
      return _MissingProject(fallbackRoute: '/');
    }
    return PtwImmersivePage(
      child: Column(
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: PtwBackButton(
              key: ValueKey(ComponentIds.evidenceBack),
              fallbackRoute: '/',
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                PtwSpacing.screenHorizontal,
                PtwSpacing.xs,
                PtwSpacing.screenHorizontal,
                PtwSpacing.md,
              ),
              children: [
                InkWell(
                  onTap: () => _pick(state),
                  borderRadius: BorderRadius.circular(PtwRadius.xl),
                  child: Container(
                    height: 170,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(
                      color: Color(project.primaryColor),
                      border: Border.all(
                        color: PtwColors.textOnAccent,
                        width: 1,
                      ),
                      borderRadius: BorderRadius.circular(PtwRadius.xl),
                    ),
                    child:
                        _media == null
                            ? Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(
                                  Icons.add_photo_alternate_rounded,
                                  color: PtwColors.textOnAccent,
                                  size: 38,
                                ),
                                const SizedBox(height: PtwSpacing.xs),
                                Text(
                                  'PHOTO · OPTIONAL',
                                  style: PtwTypography.caption.copyWith(
                                    color: PtwColors.textOnAccent,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 1.1,
                                  ),
                                ),
                              ],
                            )
                            : Stack(
                              fit: StackFit.expand,
                              children: [
                                PtwMediaImage(image: _media!),
                                const Align(
                                  alignment: Alignment.topRight,
                                  child: Padding(
                                    padding: EdgeInsets.all(PtwSpacing.xs),
                                    child: CircleAvatar(
                                      backgroundColor: PtwColors.ink,
                                      child: Icon(
                                        Icons.edit_rounded,
                                        color: PtwColors.textOnAccent,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                  ),
                ),
                const SizedBox(height: PtwSpacing.md),
                TextField(
                  key: const ValueKey(ComponentIds.evidenceTitle),
                  controller: _titleController,
                  maxLength: 70,
                  decoration: const InputDecoration(hintText: 'What happened?'),
                ),
                const SizedBox(height: PtwSpacing.md),
                TextField(
                  key: const ValueKey(ComponentIds.evidenceDetails),
                  controller: _detailsController,
                  minLines: 4,
                  maxLines: 6,
                  maxLength: 240,
                  decoration: const InputDecoration(
                    hintText: 'Why does it matter?',
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
            child: PtwBlackButton(
              key: const ValueKey(ComponentIds.addEvidencePublish),
              label: 'Publish proof',
              icon: Icons.bolt_rounded,
              onPressed: _saving ? null : () => _publish(state),
            ),
          ),
        ],
      ),
    );
  }
}

final class _MissingProject extends StatelessWidget {
  const _MissingProject({required this.fallbackRoute});

  final String fallbackRoute;

  @override
  Widget build(BuildContext context) => PtwImmersivePage(
    child: Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: PtwBackButton(fallbackRoute: fallbackRoute),
        ),
        Expanded(
          child: Center(
            child: Text(
              'Project unavailable',
              style: PtwTypography.titleLarge.copyWith(
                color: PtwColors.textOnAccent,
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
