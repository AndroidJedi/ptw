import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_image_ref.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/atoms/ptw_media_image.dart';

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
      return const Scaffold(body: Center(child: Text('Project not found')));
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Add proof')),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
                children: [
                  Text(
                    'Show the next real step.',
                    style: PtwTypography.titleLarge,
                  ),
                  const SizedBox(height: PtwSpacing.lg),
                  InkWell(
                    onTap: () => _pick(state),
                    borderRadius: BorderRadius.circular(PtwRadius.lg),
                    child: Container(
                      height: 150,
                      clipBehavior: Clip.antiAlias,
                      decoration: BoxDecoration(
                        color: Color(
                          project.primaryColor,
                        ).withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(PtwRadius.lg),
                      ),
                      child:
                          _media == null
                              ? const Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.add_photo_alternate_rounded,
                                    size: 36,
                                  ),
                                  SizedBox(height: 8),
                                  Text(
                                    'Add a photo · optional',
                                    style: PtwTypography.bodyStrong,
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
                                      padding: EdgeInsets.all(8),
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
                    decoration: const InputDecoration(
                      labelText: 'What happened?',
                      hintText: 'The first 20 people signed up',
                    ),
                  ),
                  const SizedBox(height: PtwSpacing.md),
                  TextField(
                    key: const ValueKey(ComponentIds.evidenceDetails),
                    controller: _detailsController,
                    minLines: 3,
                    maxLines: 5,
                    maxLength: 240,
                    decoration: const InputDecoration(
                      labelText: 'Why does it matter?',
                      alignLabelWithHint: true,
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
      ),
    );
  }
}
