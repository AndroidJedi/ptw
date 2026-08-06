import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import '../../core/theme/ptw_theme.dart';
import '../../core/theme/ptw_typography.dart';
import 'social_post_studio_screen.dart';
import 'studio_avatar_picker.dart';
import 'studio_models.dart';

final class SocialPostStudioApp extends StatefulWidget {
  const SocialPostStudioApp({super.key, this.catalog, this.avatarPicker});

  final MemeStickerCatalog? catalog;
  final StudioAvatarPicker? avatarPicker;

  @override
  State<SocialPostStudioApp> createState() => _SocialPostStudioAppState();
}

final class _SocialPostStudioAppState extends State<SocialPostStudioApp> {
  late final Future<MemeStickerCatalog> _catalogFuture;

  @override
  void initState() {
    super.initState();
    _catalogFuture =
        widget.catalog == null
            ? loadMemeStickerCatalog()
            : Future.value(widget.catalog);
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'PTW Story Studio',
    theme: PtwTheme.light.copyWith(
      scaffoldBackgroundColor: PtwColors.backgroundPrimary,
      inputDecorationTheme: PtwTheme.light.inputDecorationTheme.copyWith(
        counterStyle: PtwTypography.caption,
      ),
    ),
    home: FutureBuilder<MemeStickerCatalog>(
      future: _catalogFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(
              child: CircularProgressIndicator(color: PtwColors.hotPink),
            ),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return Scaffold(
            body: Center(
              child: Text(
                'Sticker collection unavailable',
                style: PtwTypography.title,
              ),
            ),
          );
        }
        return SocialPostStudioScreen(
          catalog: snapshot.requireData,
          avatarPicker: widget.avatarPicker,
        );
      },
    ),
  );
}
