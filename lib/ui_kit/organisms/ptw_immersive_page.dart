import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/ptw_colors.dart';

final class PtwImmersivePage extends StatelessWidget {
  const PtwImmersivePage({
    required this.child,
    super.key,
    this.backgroundColor = PtwColors.hotPink,
    this.decoration,
    this.safeArea = true,
  });

  final Widget child;
  final Color backgroundColor;
  final Decoration? decoration;
  final bool safeArea;

  @override
  Widget build(BuildContext context) => AnnotatedRegion<SystemUiOverlayStyle>(
    value: SystemUiOverlayStyle.light.copyWith(
      statusBarColor: PtwColors.transparent,
      systemNavigationBarColor: backgroundColor,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
    child: Scaffold(backgroundColor: backgroundColor, body: _content),
  );

  Widget get _content {
    final content =
        decoration == null
            ? child
            : DecoratedBox(decoration: decoration!, child: child);
    return safeArea ? SafeArea(child: content) : content;
  }
}
