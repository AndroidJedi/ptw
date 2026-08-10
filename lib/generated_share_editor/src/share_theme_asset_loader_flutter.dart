import 'dart:convert';

import 'package:flutter/services.dart';

Future<String> loadShareThemeAsset(String path, Object? bundle) async {
  if (bundle != null && bundle is! AssetBundle) {
    throw ArgumentError.value(bundle, 'bundle', 'Expected an AssetBundle');
  }
  final data = await (bundle as AssetBundle? ?? rootBundle).load(path);
  return utf8.decode(Uint8List.sublistView(data));
}
