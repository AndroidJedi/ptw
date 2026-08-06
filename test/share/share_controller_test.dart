import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/share/share_controller.dart';
import 'package:ptw/features/share/share_engine.dart';
import 'package:ptw/features/share/share_models.dart';
import 'package:ptw/models/ptw_image_ref.dart';
import 'package:ptw/models/ptw_project.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ShareCatalog catalog;
  late PtwProject project;

  setUpAll(() async {
    catalog = ShareCatalog.fromJson(
      jsonDecode(await rootBundle.loadString('assets/mock/share_content.json'))
          as Map<String, dynamic>,
    );
    project = PtwProject(
      id: 'project_test',
      ownerId: 'user_alex',
      ownerName: 'Alex',
      ownerHandle: 'alexbuilds',
      ownerAvatarAsset: 'assets/images/users/alex.jpg',
      goal: 'Launch something people cannot ignore',
      deadline: DateTime(2026, 10, 1),
      image: const PtwImageRef.asset('assets/images/backgrounds/startup.jpg'),
      primaryColor: 0xFFF4066E,
      status: PtwProjectStatus.active,
      createdAt: DateTime(2026, 7, 1),
    );
  });

  ShareController controller({ShareEvent event = ShareEvent.manual}) =>
      ShareController(
        engine: ShareEngine(catalog: catalog),
        project: project,
        responses: const [],
        evidence: const [],
        referenceTime: DateTime(2026, 8, 3),
        event: event,
      );

  test('event, platform, and format defaults are deterministic', () {
    final value = controller(event: ShareEvent.milestoneReached);
    addTearDown(value.dispose);

    expect(value.template, ShareTemplateType.milestone);
    expect(value.platform, SharePlatform.instagramStories);
    expect(value.format, ShareFormat.story);

    value.selectPlatform(SharePlatform.linkedin);
    expect(value.format, ShareFormat.portrait);
    value.selectFormat(ShareFormat.square);
    expect(value.format, ShareFormat.square);
    value.selectPlatform(SharePlatform.x);
    expect(value.format, ShareFormat.square);
  });

  test('variation resets manual edits but preserves platform and format', () {
    final value = controller();
    addTearDown(value.dispose);
    value.selectPlatform(SharePlatform.linkedin);
    value.selectFormat(ShareFormat.square);
    value.editCopy(hook: 'My own hook', caption: 'My own caption');

    expect(value.card.hook, 'My own hook');
    value.generateAnother();

    expect(value.variationIndex, 1);
    expect(value.card.hook, isNot('My own hook'));
    expect(value.card.caption, isNot('My own caption'));
    expect(value.platform, SharePlatform.linkedin);
    expect(value.format, ShareFormat.square);
  });

  test('all unavailable lifecycle values are disclosed as demo data', () {
    final value = controller();
    addTearDown(value.dispose);

    for (final type in const [
      ShareTemplateType.criticism,
      ShareTemplateType.milestone,
      ShareTemplateType.result,
      ShareTemplateType.opinionChange,
    ]) {
      value.selectTemplate(type);
      expect(value.card.usesFallbackData, isTrue, reason: type.name);
    }
  });
}
