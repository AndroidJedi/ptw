import 'share_face_safety_contract.dart';
import 'share_face_safety_stub.dart'
    if (dart.library.io) 'share_face_safety_mobile.dart';

export 'share_face_safety_contract.dart';

ShareFaceSafetyService createShareFaceSafetyService() =>
    createPlatformShareFaceSafetyService();
