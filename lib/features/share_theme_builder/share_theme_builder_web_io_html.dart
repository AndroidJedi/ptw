// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:html' as html;
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
  static Future<BrowserPickedFile?> pickFile({required String accept}) async {
    final input = html.FileUploadInputElement()..accept = accept;
    input.click();
    await input.onChange.first;
    final file = input.files?.firstOrNull;
    if (file == null) return null;
    final reader = html.FileReader()..readAsArrayBuffer(file);
    await reader.onLoadEnd.first;
    final result = reader.result;
    final bytes = switch (result) {
      ByteBuffer value => value.asUint8List(),
      Uint8List value => value,
      List<int> value => Uint8List.fromList(value),
      _ => throw StateError('The selected file could not be read'),
    };
    return BrowserPickedFile(
      name: file.name,
      mimeType: file.type.isEmpty ? _mimeFromName(file.name) : file.type,
      bytes: bytes,
    );
  }

  static void download({
    required String fileName,
    required List<int> bytes,
    required String mimeType,
  }) {
    final blob = html.Blob([bytes], mimeType);
    final url = html.Url.createObjectUrlFromBlob(blob);
    try {
      (html.AnchorElement(href: url)
            ..download = fileName
            ..style.display = 'none')
          .click();
    } finally {
      html.Url.revokeObjectUrl(url);
    }
  }

  static String _mimeFromName(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.json')) return 'application/json';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
      return 'image/jpeg';
    }
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.ttf')) return 'font/ttf';
    if (lower.endsWith('.otf')) return 'font/otf';
    if (lower.endsWith('.zip')) return 'application/zip';
    return 'image/png';
  }
}

extension _FirstOrNull<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
