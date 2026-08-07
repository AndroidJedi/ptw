import 'dart:ui';

import 'package:share_plus/share_plus.dart';

import 'share_models.dart';

enum PtwShareResultStatus { success, dismissed, unavailable }

final class PtwShareResult {
  const PtwShareResult({required this.status, this.target});

  final PtwShareResultStatus status;
  final String? target;
}

abstract interface class PtwShareService {
  Future<PtwShareResult> share({
    required ShareAsset asset,
    required String text,
    required Rect sharePositionOrigin,
  });
}

final class NativePtwShareService implements PtwShareService {
  const NativePtwShareService();

  @override
  Future<PtwShareResult> share({
    required ShareAsset asset,
    required String text,
    required Rect sharePositionOrigin,
  }) async {
    final result = await SharePlus.instance.share(
      ShareParams(
        title: 'Share your challenge',
        text: text,
        files: [XFile.fromData(asset.bytes, mimeType: asset.mimeType)],
        fileNameOverrides: [asset.fileName],
        sharePositionOrigin: sharePositionOrigin,
      ),
    );
    return PtwShareResult(
      status: switch (result.status) {
        ShareResultStatus.success => PtwShareResultStatus.success,
        ShareResultStatus.dismissed => PtwShareResultStatus.dismissed,
        ShareResultStatus.unavailable => PtwShareResultStatus.unavailable,
      },
      target: result.raw.isEmpty ? null : result.raw,
    );
  }
}
