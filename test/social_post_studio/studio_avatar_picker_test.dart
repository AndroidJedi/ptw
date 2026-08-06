import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:ptw/features/social_post_studio/social_post_studio_controller.dart';
import 'package:ptw/features/social_post_studio/studio_avatar_picker.dart';

void main() {
  test('accepts PNG, JPEG, and WebP browser files', () async {
    for (final mime in const ['image/png', 'image/jpeg', 'image/webp']) {
      final picker = BrowserStudioAvatarPicker(
        pickImage:
            () async => XFile.fromData(
              Uint8List.fromList([1, 2, 3]),
              mimeType: mime,
              name: 'avatar',
            ),
      );

      final selection = await picker.pickAvatar();
      expect(selection!.mimeType, mime);
      expect(selection.bytes, [1, 2, 3]);
    }
  });

  test('rejects unsupported and oversized files', () async {
    final unsupported = BrowserStudioAvatarPicker(
      pickImage:
          () async => XFile.fromData(
            Uint8List.fromList([1]),
            mimeType: 'image/gif',
            name: 'avatar.gif',
          ),
    );
    final oversized = BrowserStudioAvatarPicker(
      pickImage:
          () async => XFile.fromData(
            Uint8List(SocialPostStudioController.maximumAvatarBytes + 1),
            mimeType: 'image/png',
            name: 'avatar.png',
          ),
    );

    await expectLater(
      unsupported.pickAvatar(),
      throwsA(isA<StudioAvatarPickException>()),
    );
    await expectLater(
      oversized.pickAvatar(),
      throwsA(isA<StudioAvatarPickException>()),
    );
  });
}
