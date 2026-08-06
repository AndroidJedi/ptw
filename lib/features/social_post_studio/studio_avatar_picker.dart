import 'dart:typed_data';

import 'package:image_picker/image_picker.dart';

import 'social_post_studio_controller.dart';

final class StudioAvatarSelection {
  const StudioAvatarSelection({required this.bytes, required this.mimeType});

  final Uint8List bytes;
  final String mimeType;
}

final class StudioAvatarPickException implements Exception {
  const StudioAvatarPickException(this.message);

  final String message;

  @override
  String toString() => message;
}

abstract interface class StudioAvatarPicker {
  Future<StudioAvatarSelection?> pickAvatar();
}

typedef PickStudioImage = Future<XFile?> Function();

final class BrowserStudioAvatarPicker implements StudioAvatarPicker {
  BrowserStudioAvatarPicker({PickStudioImage? pickImage})
    : _pickImage =
          pickImage ??
          (() => ImagePicker().pickImage(
            source: ImageSource.gallery,
            maxWidth: 2048,
          ));

  static const _supportedMimeTypes = {'image/jpeg', 'image/png', 'image/webp'};

  final PickStudioImage _pickImage;

  @override
  Future<StudioAvatarSelection?> pickAvatar() async {
    final file = await _pickImage();
    if (file == null) return null;
    final mimeType = _resolveMimeType(file);
    if (!_supportedMimeTypes.contains(mimeType)) {
      throw const StudioAvatarPickException(
        'Choose a PNG, JPEG, or WebP image.',
      );
    }
    final bytes = await file.readAsBytes();
    if (bytes.isEmpty) {
      throw const StudioAvatarPickException('That image is empty.');
    }
    if (bytes.length > SocialPostStudioController.maximumAvatarBytes) {
      throw const StudioAvatarPickException(
        'Choose an avatar smaller than 10 MB.',
      );
    }
    return StudioAvatarSelection(bytes: bytes, mimeType: mimeType);
  }

  String _resolveMimeType(XFile file) {
    final provided = file.mimeType?.toLowerCase();
    if (provided != null && provided.isNotEmpty) return provided;
    final path = file.path.toLowerCase();
    if (path.endsWith('.png')) return 'image/png';
    if (path.endsWith('.webp')) return 'image/webp';
    if (path.endsWith('.jpg') || path.endsWith('.jpeg')) return 'image/jpeg';
    return 'application/octet-stream';
  }
}
