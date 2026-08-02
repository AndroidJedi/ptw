import 'dart:io';

import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import '../../models/ptw_image_ref.dart';
import '../../state/ptw_app_state.dart';

final class PtwMediaImage extends StatelessWidget {
  const PtwMediaImage({
    required this.image,
    super.key,
    this.fit = BoxFit.cover,
  });

  final PtwImageRef image;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final error = Container(
      color: PtwColors.ink,
      alignment: Alignment.center,
      child: const Icon(
        Icons.broken_image_outlined,
        color: PtwColors.textOnAccent,
        size: 36,
      ),
    );
    if (image.source == PtwImageSource.asset) {
      return Image.asset(
        image.path,
        fit: fit,
        errorBuilder: (_, __, ___) => error,
      );
    }
    final path = PtwScope.of(context).mediaService.resolveFilePath(image);
    return Image.file(
      File(path),
      fit: fit,
      errorBuilder: (_, __, ___) => error,
    );
  }
}
