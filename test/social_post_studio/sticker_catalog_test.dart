import 'dart:ui' as ui;

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ptw/features/social_post_studio/studio_models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('catalog defines four ordered stickers in every category', () async {
    final catalog = await loadMemeStickerCatalog();

    expect(catalog.stickers, hasLength(12));
    expect(catalog.stickers.map((item) => item.id).toSet(), hasLength(12));
    expect(
      catalog.stickers.map((item) => item.order),
      orderedEquals(List.generate(12, (index) => index)),
    );
    for (final category in MemeStickerCategory.values) {
      expect(catalog.inCategory(category), hasLength(4));
    }
  });

  test(
    'every sticker is a 512px transparent PNG with visible content',
    () async {
      final catalog = await loadMemeStickerCatalog();

      for (final sticker in catalog.stickers) {
        final data = await rootBundle.load(sticker.assetPath);
        final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
        final frame = await codec.getNextFrame();
        final image = frame.image;
        final rgba = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
        expect(image.width, 512, reason: sticker.id);
        expect(image.height, 512, reason: sticker.id);
        expect(rgba, isNotNull, reason: sticker.id);
        final bytes = rgba!.buffer.asUint8List();
        final cornerAlpha = <int>[
          bytes[3],
          bytes[(image.width - 1) * 4 + 3],
          bytes[((image.height - 1) * image.width) * 4 + 3],
          bytes[(image.width * image.height - 1) * 4 + 3],
        ];
        expect(cornerAlpha, everyElement(0), reason: sticker.id);
        expect(
          Iterable.generate(
            image.width * image.height,
            (index) => bytes[index * 4 + 3],
          ).any((alpha) => alpha == 255),
          isTrue,
          reason: sticker.id,
        );
        image.dispose();
        codec.dispose();
      }
    },
  );

  test('catalog rejects duplicate identifiers', () {
    const item = MemeStickerDefinition(
      id: 'same',
      label: 'Same',
      category: MemeStickerCategory.hype,
      assetPath: 'asset.png',
      order: 0,
      defaultScale: 0.2,
    );

    expect(
      () => MemeStickerCatalog(stickers: const [item, item]),
      throwsFormatException,
    );
  });
}
