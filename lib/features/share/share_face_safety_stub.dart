import '../../models/ptw_image_ref.dart';
import 'share_face_safety_contract.dart';

ShareFaceSafetyService createPlatformShareFaceSafetyService() =>
    const _UnsupportedShareFaceSafetyService();

final class _UnsupportedShareFaceSafetyService
    implements ShareFaceSafetyService {
  const _UnsupportedShareFaceSafetyService();

  @override
  Future<bool> canUseSemanticStickers(
    PtwImageRef image, {
    required String Function(PtwImageRef image) resolveFilePath,
  }) async => false;
}
