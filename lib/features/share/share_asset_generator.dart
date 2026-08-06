import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

import '../../core/theme/ptw_colors.dart';
import 'share_card.dart';
import 'share_models.dart';

final class ShareAssetGenerator {
  const ShareAssetGenerator();

  Future<ShareAsset> generate({
    required BuildContext context,
    required ShareCardData data,
    required ShareFormat format,
  }) async {
    final boundaryKey = GlobalKey();
    final logicalHeight = 360 / format.aspectRatio;
    final overlay = Overlay.of(context, rootOverlay: true);
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
                  child: SizedBox(
                    width: 360,
                    height: logicalHeight,
                    child: ShareCard(data: data, format: format),
                  ),
                ),
              ),
            ),
          ),
    );
    overlay.insert(entry);
    try {
      for (var attempt = 0; attempt < 4; attempt++) {
        WidgetsBinding.instance.scheduleFrame();
        await WidgetsBinding.instance.endOfFrame;
        final boundary =
            boundaryKey.currentContext?.findRenderObject()
                as RenderRepaintBoundary?;
        if (boundary != null && !boundary.debugNeedsPaint) {
          return await capture(
            boundaryKey: boundaryKey,
            format: format,
            projectId: data.projectId,
          );
        }
      }
      throw StateError('Share card did not finish painting');
    } finally {
      entry.remove();
    }
  }

  Future<ShareAsset> capture({
    required GlobalKey boundaryKey,
    required ShareFormat format,
    required String projectId,
  }) async {
    final boundary =
        boundaryKey.currentContext?.findRenderObject()
            as RenderRepaintBoundary?;
    if (boundary == null || boundary.debugNeedsPaint) {
      throw StateError('Share card is not ready to capture');
    }
    final pixelRatio = format.width / boundary.size.width;
    final image = await boundary.toImage(pixelRatio: pixelRatio);
    try {
      if (image.width != format.width || image.height != format.height) {
        throw StateError(
          'Unexpected share asset size: ${image.width}x${image.height}',
        );
      }
      final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
      if (byteData == null) {
        throw StateError('Share card could not be encoded');
      }
      final bytes = Uint8List.sublistView(byteData);
      return ShareAsset(
        bytes: bytes,
        format: format,
        fileName: 'ptw_${projectId}_${format.name}.png',
      );
    } finally {
      image.dispose();
    }
  }
}
