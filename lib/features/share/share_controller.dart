import 'package:flutter/foundation.dart';

import '../../models/ptw_evidence.dart';
import '../../models/ptw_project.dart';
import '../../models/ptw_response.dart';
import 'share_engine.dart';
import 'share_models.dart';

final class ShareController extends ChangeNotifier {
  ShareController({
    required this.engine,
    required this.project,
    required this.responses,
    required this.evidence,
    required this.referenceTime,
    this.event = ShareEvent.manual,
    ShareTemplateType? initialTemplate,
  }) : _template = initialTemplate ?? event.recommendedTemplate,
       _format = ShareFormat.story;

  final ShareEngine engine;
  final PtwProject project;
  final List<PtwResponse> responses;
  final List<PtwEvidence> evidence;
  final DateTime referenceTime;
  final ShareEvent event;

  ShareTemplateType _template;
  ShareFormat _format;
  int _variationIndex = 0;
  String? _hookOverride;
  String? _captionOverride;

  ShareTemplateType get template => _template;
  ShareFormat get format => _format;
  int get variationIndex => _variationIndex;

  ShareCardData get generatedCard => engine.buildCard(
    project: project,
    responses: responses,
    evidence: evidence,
    template: _template,
    event: event,
    variationIndex: _variationIndex,
    referenceTime: referenceTime,
  );

  ShareCardData get card =>
      generatedCard.copyWith(hook: _hookOverride, caption: _captionOverride);

  String get captionWithLink => engine.copyGenerator.captionWithLink(card);

  void selectTemplate(ShareTemplateType value) {
    if (value == _template) return;
    _template = value;
    _variationIndex = 0;
    _clearEdits();
    notifyListeners();
  }

  void selectFormat(ShareFormat value) {
    if (value == _format) return;
    _format = value;
    notifyListeners();
  }

  void generateAnother() {
    final count = engine.catalog.template(_template).variations.length;
    _variationIndex = (_variationIndex + 1) % count;
    _clearEdits();
    notifyListeners();
  }

  void editCopy({required String hook, required String caption}) {
    _hookOverride = hook.trim();
    _captionOverride = caption.trim();
    notifyListeners();
  }

  void _clearEdits() {
    _hookOverride = null;
    _captionOverride = null;
  }
}
