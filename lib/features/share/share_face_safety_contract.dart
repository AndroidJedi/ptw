import '../../models/ptw_image_ref.dart';

abstract interface class ShareFaceSafetyService {
  Future<bool> canUseSemanticStickers(
    PtwImageRef image, {
    required String Function(PtwImageRef image) resolveFilePath,
  });
}
