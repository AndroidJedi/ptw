import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:ptw/core/data/ptw_media_service.dart';
import 'package:ptw/models/ptw_image_ref.dart';

void main() {
  late Directory temporaryDirectory;

  setUp(() async {
    temporaryDirectory = await Directory.systemTemp.createTemp(
      'ptw_share_media_test_',
    );
  });

  tearDown(() async {
    if (await temporaryDirectory.exists()) {
      await temporaryDirectory.delete(recursive: true);
    }
  });

  test(
    'share imports are resized and stored as durable file references',
    () async {
      final source = File('${temporaryDirectory.path}/chosen.webp');
      await source.writeAsBytes(const [82, 73, 70, 70]);
      double? requestedWidth;
      double? requestedHeight;
      int? requestedQuality;
      final service = LocalPtwMediaService(
        documentsDirectory: temporaryDirectory,
        galleryPicker: ({
          required maxWidth,
          required maxHeight,
          imageQuality,
        }) async {
          requestedWidth = maxWidth;
          requestedHeight = maxHeight;
          requestedQuality = imageQuality;
          return XFile(source.path);
        },
      );

      final result = await service.pickShareImage(
        PtwShareImagePurpose.background,
      );

      expect(requestedWidth, 2048);
      expect(requestedHeight, 2048);
      expect(requestedQuality, 90);
      expect(result?.source, PtwImageSource.file);
      expect(result?.path, startsWith('ptw_media/share_'));
      expect(result?.path, endsWith('.webp'));
      expect(File(service.resolveFilePath(result!)).existsSync(), isTrue);
    },
  );

  test('decoration imports preserve transparency', () async {
    final source = File('${temporaryDirectory.path}/sticker.png');
    await source.writeAsBytes(const [137, 80, 78, 71]);
    int? requestedQuality = -1;
    final service = LocalPtwMediaService(
      documentsDirectory: temporaryDirectory,
      galleryPicker: ({
        required maxWidth,
        required maxHeight,
        imageQuality,
      }) async {
        requestedQuality = imageQuality;
        return XFile(source.path);
      },
    );

    await service.pickShareImage(PtwShareImagePurpose.decoration);

    expect(requestedQuality, isNull);
  });

  test(
    'unsupported and oversized share imports show actionable errors',
    () async {
      final unsupported = File('${temporaryDirectory.path}/sticker.gif');
      await unsupported.writeAsBytes(const [71, 73, 70]);
      final unsupportedService = LocalPtwMediaService(
        documentsDirectory: temporaryDirectory,
        galleryPicker:
            ({required maxWidth, required maxHeight, imageQuality}) async =>
                XFile(unsupported.path),
      );
      expect(
        () =>
            unsupportedService.pickShareImage(PtwShareImagePurpose.decoration),
        throwsA(
          isA<PtwMediaException>().having(
            (error) => error.message,
            'message',
            contains('PNG, JPEG, or WebP'),
          ),
        ),
      );

      final oversized = File('${temporaryDirectory.path}/large.jpg');
      final handle = await oversized.open(mode: FileMode.write);
      await handle.truncate(LocalPtwMediaService.maximumShareImageBytes + 1);
      await handle.close();
      final oversizedService = LocalPtwMediaService(
        documentsDirectory: temporaryDirectory,
        galleryPicker:
            ({required maxWidth, required maxHeight, imageQuality}) async =>
                XFile(oversized.path),
      );
      expect(
        () => oversizedService.pickShareImage(PtwShareImagePurpose.background),
        throwsA(
          isA<PtwMediaException>().having(
            (error) => error.message,
            'message',
            contains('10 MB'),
          ),
        ),
      );
    },
  );
}
