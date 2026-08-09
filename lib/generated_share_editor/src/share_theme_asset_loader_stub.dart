Future<String> loadShareThemeAsset(String path, Object? bundle) =>
    Future<String>.error(
      UnsupportedError(
        'Flutter asset loading is unavailable in a plain Dart process. '
        'Read the file and use ShareThemeBundle.fromJsonString instead.',
      ),
    );
