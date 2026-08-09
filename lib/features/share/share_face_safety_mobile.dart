import 'dart:io';

import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';

import '../../models/ptw_image_ref.dart';
import 'share_face_safety_contract.dart';

ShareFaceSafetyService createPlatformShareFaceSafetyService() =>
    const MobileShareFaceSafetyService();

/// Conservative face safety: any detected face suppresses all stickers.
/// Unsupported assets, detector failures, and uncertain inputs also suppress.
final class MobileShareFaceSafetyService implements ShareFaceSafetyService {
  const MobileShareFaceSafetyService();

  @override
  Future<bool> canUseSemanticStickers(
    PtwImageRef image, {
    required String Function(PtwImageRef image) resolveFilePath,
  }) async {
    if (!Platform.isAndroid && !Platform.isIOS) return false;
    if (image.source != PtwImageSource.file) return false;
    final detector = FaceDetector(
      options: FaceDetectorOptions(
        performanceMode: FaceDetectorMode.fast,
        enableContours: false,
        enableLandmarks: false,
        enableClassification: false,
      ),
    );
    try {
      final input = InputImage.fromFilePath(resolveFilePath(image));
      final faces = await detector.processImage(input);
      return faces.isEmpty;
    } on Object {
      return false;
    } finally {
      await detector.close();
    }
  }
}
