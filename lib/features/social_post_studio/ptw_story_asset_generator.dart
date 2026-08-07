import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

import '../../core/theme/ptw_colors.dart';
import '../../models/ptw_story_composition.dart';
import '../share/share_models.dart';
import 'ptw_story_card.dart';
import 'studio_models.dart';

final class PtwStoryAssetGenerator {
  const PtwStoryAssetGenerator();

  Future<ShareAsset> generate({
    required BuildContext context,
    required PtwStoryComposition composition,
    required MemeStickerCatalog catalog,
  }) async {
    final boundaryKey = GlobalKey();
    final entry = OverlayEntry(
      builder:
          (_) => IgnorePointer(
            child: ColorFiltered(
              colorFilter: const ColorFilter.mode(
                PtwColors.transparent,
                BlendMode.srcIn,
              ),
              child: OverflowBox(
                alignment: Alignment.topLeft,
                minWidth: 0,
                minHeight: 0,
                maxWidth: double.infinity,
                maxHeight: double.infinity,
                child: RepaintBoundary(
                  key: boundaryKey,
                  child: SizedBox.fromSize(
                    size: PtwStoryCard.logicalSize,
                    child: PtwStoryCard(
                      composition: composition,
                      catalog: catalog,
                    ),
                  ),
                ),
              ),
            ),
          ),
    );
    Overlay.of(context, rootOverlay: true).insert(entry);
    try {
      for (var attempt = 0; attempt < 4; attempt++) {
        WidgetsBinding.instance.scheduleFrame();
        await WidgetsBinding.instance.endOfFrame;
        final boundary =
            boundaryKey.currentContext?.findRenderObject()
                as RenderRepaintBoundary?;
        if (boundary != null && !boundary.debugNeedsPaint) {
          return _capture(boundary, composition.projectId);
        }
      }
      throw StateError('Story did not finish painting');
    } finally {
      entry.remove();
    }
  }

  Future<ShareAsset> _capture(
    RenderRepaintBoundary boundary,
    String projectId,
  ) async {
    final image = await boundary.toImage(pixelRatio: 3);
    try {
      if (image.width != 1080 || image.height != 1920) {
        throw StateError(
          'Unexpected Story size: ${image.width}x${image.height}',
        );
      }
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      if (data == null) throw StateError('Story could not be encoded');
      return ShareAsset(
        bytes: Uint8List.sublistView(data),
        format: ShareFormat.story,
        fileName: 'ptw_${projectId}_story.png',
      );
    } finally {
      image.dispose();
    }
  }

  Future<ShareAsset> capture({
    required GlobalKey boundaryKey,
    required String projectId,
  }) async {
    final boundary =
        boundaryKey.currentContext?.findRenderObject()
            as RenderRepaintBoundary?;
    if (boundary == null || boundary.debugNeedsPaint) {
      throw StateError('Story is not ready to capture');
    }
    return _capture(boundary, projectId);
  }
}
