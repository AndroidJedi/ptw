import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/ptw_colors.dart';
import '../core/theme/ptw_spacing.dart';
import '../core/theme/ptw_theme.dart';
import '../core/theme/ptw_typography.dart';
import '../core/data/ptw_media_service.dart';
import '../core/data/ptw_prototype_repository.dart';
import '../state/ptw_app_state.dart';
import '../ui_kit/atoms/ptw_black_button.dart';
import '../ui_kit/organisms/ptw_immersive_page.dart';
import 'app_router.dart';

/// Root application that loads mock assets before exposing the router.
final class PtwApp extends StatefulWidget {
  const PtwApp({
    super.key,
    this.initialLocation,
    this.repository,
    this.mediaService,
    this.now,
  });

  final String? initialLocation;
  final PtwPrototypeRepository? repository;
  final PtwMediaService? mediaService;
  final DateTime Function()? now;

  @override
  State<PtwApp> createState() => _PtwAppState();
}

final class _PtwAppState extends State<PtwApp> {
  late final PtwAppState _state;
  late final Future<void> _loadFuture;
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _state = PtwAppState(
      repository: widget.repository,
      mediaService: widget.mediaService,
      now: widget.now,
    );
    _loadFuture = _state.load();
    _router = AppRouter.create(initialLocation: widget.initialLocation ?? '/');
  }

  @override
  void dispose() {
    _router.dispose();
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<void>(
    future: _loadFuture,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: PtwTheme.light,
          home: const PtwImmersivePage(
            child: Center(
              child: CircularProgressIndicator(color: PtwColors.textOnAccent),
            ),
          ),
        );
      }
      if (!_state.isReady) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: PtwTheme.light,
          home: PtwImmersivePage(
            child: Padding(
              padding: const EdgeInsets.all(PtwSpacing.lg),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.warning_amber_rounded,
                      color: PtwColors.textOnAccent,
                      size: 48,
                    ),
                    const SizedBox(height: PtwSpacing.md),
                    Text(
                      'Local data unavailable',
                      textAlign: TextAlign.center,
                      style: PtwTypography.titleLarge.copyWith(
                        color: PtwColors.textOnAccent,
                      ),
                    ),
                    const SizedBox(height: PtwSpacing.md),
                    PtwBlackButton(
                      label: 'Reset local prototype',
                      onPressed: () async {
                        await _state.reset();
                        if (mounted) setState(() {});
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      }
      return PtwScope(
        state: _state,
        child: MaterialApp.router(
          debugShowCheckedModeBanner: false,
          title: 'PTW — Prove Them Wrong',
          theme: PtwTheme.light,
          routerConfig: _router,
        ),
      );
    },
  );
}
