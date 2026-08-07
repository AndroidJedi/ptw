import 'dart:typed_data';

final class BrowserPickedFile {
  const BrowserPickedFile({
    required this.name,
    required this.mimeType,
    required this.bytes,
  });

  final String name;
  final String mimeType;
  final Uint8List bytes;
}

abstract final class ShareThemeBuilderWebIo {
  static Future<BrowserPickedFile?> pickFile({required String accept}) =>
      throw UnsupportedError('File picking is available in the web builder');

  static void download({
    required String fileName,
    required List<int> bytes,
    required String mimeType,
  }) => throw UnsupportedError('Downloads are available in the web builder');
}
