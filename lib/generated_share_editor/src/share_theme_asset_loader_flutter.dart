import 'package:flutter/services.dart';

Future<String> loadShareThemeAsset(String path, Object? bundle) {
  if (bundle != null && bundle is! AssetBundle) {
    throw ArgumentError.value(bundle, 'bundle', 'Expected an AssetBundle');
  }
  return (bundle as AssetBundle? ?? rootBundle).loadString(path);
}
