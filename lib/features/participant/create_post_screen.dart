import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/component_ids.dart';
import '../../core/formatters/ptw_formatters.dart';
import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_radius.dart';
import '../../core/theme/ptw_spacing.dart';
import '../../core/theme/ptw_typography.dart';
import '../../models/ptw_image_ref.dart';
import '../../models/ptw_project.dart';
import '../../state/ptw_app_state.dart';
import '../../ui_kit/atoms/ptw_back_button.dart';
import '../../ui_kit/atoms/ptw_black_button.dart';
import '../../ui_kit/organisms/ptw_immersive_page.dart';
import '../../ui_kit/organisms/ptw_project_tile.dart';

final class CreatePostScreen extends StatefulWidget {
  const CreatePostScreen({super.key});

  @override
  State<CreatePostScreen> createState() => _CreatePostScreenState();
}

final class _CreatePostScreenState extends State<CreatePostScreen> {
  final _goalController = TextEditingController();
  DateTime? _deadline;
  PtwImageRef? _image;
  int? _primaryColor;
  int _step = 0;
  bool _saving = false;

  @override
  void dispose() {
    _goalController.dispose();
    super.dispose();
  }

  Future<void> _pickDeadline() async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final result = await showDatePicker(
      context: context,
      initialDate: today.add(const Duration(days: 30)),
      firstDate: today,
      lastDate: DateTime(today.year + 5, 12, 31),
    );
    if (result != null) setState(() => _deadline = result);
  }

  void _continue() {
    final goal = _goalController.text.trim();
    if (goal.isEmpty || goal.length > 90 || _deadline == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add a clear goal and a deadline.')),
      );
      return;
    }
    setState(() => _step = 1);
  }

  Future<void> _pickDeviceImage(PtwAppState state) async {
    try {
      final image = await state.mediaService.pickProjectImage();
      if (image != null && mounted) setState(() => _image = image);
    } on Exception {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('That photo could not be imported.')),
      );
    }
  }

  Future<void> _publish(PtwAppState state) async {
    if (_image == null || _primaryColor == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose a project image and color.')),
      );
      return;
    }
    setState(() => _saving = true);
    try {
      final project = await state.createProject(
        goal: _goalController.text,
        deadline: _deadline!,
        image: _image!,
        primaryColor: _primaryColor!,
      );
      if (mounted) context.go('/projects/${project.id}/share');
    } on Exception {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Project could not be saved. Try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = PtwScope.of(context);
    _image ??= state.recoveredProjectImage;
    return PtwImmersivePage(
      key: const ValueKey(ComponentIds.createProjectScreen),
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: PtwBackButton(
              key: const ValueKey(ComponentIds.createProjectBack),
              fallbackRoute: '/',
              onPressed: _step == 0 ? null : () => setState(() => _step = 0),
            ),
          ),
          Expanded(child: _step == 0 ? _goalStep() : _visualStep(state)),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 16),
            child: PtwBlackButton(
              key: ValueKey(
                _step == 0
                    ? ComponentIds.createProjectContinue
                    : ComponentIds.createProjectPublish,
              ),
              label: _step == 0 ? 'Continue' : 'Create & share',
              icon:
                  _step == 0 ? Icons.arrow_forward_rounded : Icons.bolt_rounded,
              onPressed:
                  _saving
                      ? null
                      : (_step == 0 ? _continue : () => _publish(state)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _goalStep() => ListView(
    padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
    children: [
      Text(
        'What will you prove?',
        style: PtwTypography.display.copyWith(color: PtwColors.textOnAccent),
      ),
      const SizedBox(height: PtwSpacing.xl),
      TextField(
        key: const ValueKey(ComponentIds.createProjectGoal),
        controller: _goalController,
        maxLength: 90,
        minLines: 3,
        maxLines: 4,
        style: PtwTypography.title,
        decoration: const InputDecoration(
          hintText: 'Launch my product and reach 100 active users',
          alignLabelWithHint: true,
        ),
      ),
      const SizedBox(height: PtwSpacing.md),
      InkWell(
        key: const ValueKey(ComponentIds.createProjectDeadline),
        onTap: _pickDeadline,
        borderRadius: BorderRadius.circular(PtwRadius.lg),
        child: Container(
          padding: const EdgeInsets.all(PtwSpacing.md),
          decoration: BoxDecoration(
            color: PtwColors.transparent,
            border: Border.all(color: PtwColors.textOnAccent, width: 1),
            borderRadius: BorderRadius.circular(PtwRadius.lg),
          ),
          child: Row(
            children: [
              const CircleAvatar(
                backgroundColor: PtwColors.ink,
                child: Icon(Icons.flag_rounded, color: PtwColors.textOnAccent),
              ),
              const SizedBox(width: PtwSpacing.sm),
              Expanded(
                child: Text(
                  _deadline == null
                      ? 'Choose a deadline'
                      : PtwFormatters.deadline(_deadline!),
                  style: PtwTypography.bodyStrong.copyWith(
                    color: PtwColors.textOnAccent,
                  ),
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                color: PtwColors.textOnAccent,
              ),
            ],
          ),
        ),
      ),
    ],
  );

  Widget _visualStep(PtwAppState state) {
    final preview =
        _image == null
            ? null
            : PtwProject(
              id: 'preview',
              ownerId: state.currentUser.id,
              ownerName: state.currentUser.name,
              ownerHandle: state.currentUser.handle,
              ownerAvatarAsset: state.currentUser.avatarAsset,
              goal: _goalController.text.trim(),
              deadline: _deadline!,
              image: _image!,
              primaryColor: _primaryColor ?? PtwColors.hotPink.toARGB32(),
              status: PtwProjectStatus.active,
              createdAt: DateTime.now(),
            );
    return ListView(
      padding: const EdgeInsets.all(PtwSpacing.screenHorizontal),
      children: [
        if (preview == null)
          Container(
            height: 270,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: PtwColors.ink,
              border: Border.all(color: PtwColors.textOnAccent, width: 1),
              borderRadius: BorderRadius.circular(PtwRadius.xl),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(
                  Icons.add_photo_alternate_rounded,
                  color: PtwColors.textOnAccent,
                  size: 52,
                ),
                const SizedBox(height: PtwSpacing.sm),
                Text(
                  'Choose the image below',
                  style: PtwTypography.title.copyWith(
                    color: PtwColors.textOnAccent,
                  ),
                ),
              ],
            ),
          )
        else
          PtwProjectTile(project: preview, height: 270, compact: true),
        const SizedBox(height: PtwSpacing.lg),
        Text(
          'IMAGE',
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.1,
          ),
        ),
        const SizedBox(height: PtwSpacing.xs),
        SizedBox(
          key: const ValueKey(ComponentIds.createProjectCuratedImages),
          height: 96,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: state.curatedImages.length + 1,
            separatorBuilder: (_, __) => const SizedBox(width: PtwSpacing.xs),
            itemBuilder: (context, index) {
              if (index == 0) {
                return InkWell(
                  key: const ValueKey(ComponentIds.createProjectDeviceImage),
                  onTap: () => _pickDeviceImage(state),
                  borderRadius: BorderRadius.circular(PtwRadius.md),
                  child: Container(
                    width: 96,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: PtwColors.ink,
                      border: Border.all(
                        color: PtwColors.textOnAccent,
                        width: 1,
                      ),
                      borderRadius: BorderRadius.circular(PtwRadius.md),
                    ),
                    child: const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.photo_library_rounded,
                          color: PtwColors.textOnAccent,
                        ),
                        SizedBox(height: 4),
                        Text(
                          'My photo',
                          style: TextStyle(
                            color: PtwColors.textOnAccent,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }
              final curated = state.curatedImages[index - 1];
              final selected =
                  _image?.source == PtwImageSource.asset &&
                  _image?.path == curated.asset;
              return InkWell(
                key: ValueKey('curated_${curated.id}'),
                onTap:
                    () => setState(
                      () => _image = PtwImageRef.asset(curated.asset),
                    ),
                borderRadius: BorderRadius.circular(PtwRadius.md),
                child: Container(
                  width: 96,
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(PtwRadius.md),
                    border: Border.all(
                      color: PtwColors.textOnAccent,
                      width: selected ? 3 : 1,
                    ),
                  ),
                  child: Image.asset(curated.asset, fit: BoxFit.cover),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: PtwSpacing.lg),
        Text(
          'COLOR',
          style: PtwTypography.caption.copyWith(
            color: PtwColors.textOnAccent,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.1,
          ),
        ),
        const SizedBox(height: PtwSpacing.xs),
        Row(
          key: const ValueKey(ComponentIds.createProjectPalette),
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            for (final color in PtwColors.projectPalette)
              InkWell(
                key: ValueKey('color_${color.toARGB32()}'),
                onTap: () => setState(() => _primaryColor = color.toARGB32()),
                customBorder: const CircleBorder(),
                child: Container(
                  width: 46,
                  height: 46,
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: PtwColors.textOnAccent,
                      width: _primaryColor == color.toARGB32() ? 3 : 1,
                    ),
                  ),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
