import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

import 'share_renderer.dart';
import 'share_theme.dart';
import 'share_value.dart';

final class SharePngAsset {
  const SharePngAsset({
    required this.bytes,
    required this.width,
    required this.height,
    required this.fileName,
  });

  final Uint8List bytes;
  final int width;
  final int height;
  final String fileName;
}

final class SharePngExporter {
  const SharePngExporter();

  Future<SharePngAsset> generate({
    required BuildContext context,
    required ShareThemeConfig theme,
    required ShareEditorContent content,
    required ShareEditorValue value,
    ShareComponentRegistry? registry,
    ShareImageProviderResolver imageResolver = defaultShareImageResolver,
    String? fileName,
  }) async {
    final key = GlobalKey();
    final entry = OverlayEntry(
      builder:
          (_) => IgnorePointer(
            child: OverflowBox(
              alignment: Alignment.topLeft,
              minWidth: 0,
              minHeight: 0,
              maxWidth: double.infinity,
              maxHeight: double.infinity,
              child: RepaintBoundary(
                key: key,
                child: SizedBox(
                  width: theme.canvas.width,
                  height: theme.canvas.height,
                  child: GeneratedShareRenderer(
                    theme: theme,
                    content: content,
                    value: value,
                    registry: registry,
                    imageResolver: imageResolver,
                    showSelection: false,
                  ),
                ),
              ),
            ),
          ),
    );
    Overlay.of(context, rootOverlay: true).insert(entry);
    try {
      for (var attempt = 0; attempt < 5; attempt++) {
        WidgetsBinding.instance.scheduleFrame();
        await WidgetsBinding.instance.endOfFrame;
        final boundary =
            key.currentContext?.findRenderObject() as RenderRepaintBoundary?;
        if (boundary != null && !boundary.debugNeedsPaint) {
          return _capture(
            boundary,
            theme,
            fileName ?? 'share_${content.projectId}.png',
          );
        }
      }
      throw StateError('Share composition did not finish painting');
    } finally {
      entry.remove();
    }
  }

  Future<SharePngAsset> capture({
    required GlobalKey boundaryKey,
    required ShareThemeConfig theme,
    required String fileName,
  }) async {
    final boundary =
        boundaryKey.currentContext?.findRenderObject()
            as RenderRepaintBoundary?;
    if (boundary == null || boundary.debugNeedsPaint) {
      throw StateError('Share composition is not ready to capture');
    }
    return _capture(boundary, theme, fileName);
  }

  Future<SharePngAsset> _capture(
    RenderRepaintBoundary boundary,
    ShareThemeConfig theme,
    String fileName,
  ) async {
    final pixelRatio = theme.canvas.outputWidth / theme.canvas.width;
    final image = await boundary.toImage(pixelRatio: pixelRatio);
    try {
      if (image.width != theme.canvas.outputWidth ||
          image.height != theme.canvas.outputHeight) {
        throw StateError(
          'Unexpected share image size: ${image.width}x${image.height}; '
          'expected ${theme.canvas.outputWidth}x${theme.canvas.outputHeight}',
        );
      }
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      if (data == null) throw StateError('Share image could not be encoded');
      return SharePngAsset(
        bytes: Uint8List.sublistView(data),
        width: image.width,
        height: image.height,
        fileName: fileName,
      );
    } finally {
      image.dispose();
    }
  }
}
