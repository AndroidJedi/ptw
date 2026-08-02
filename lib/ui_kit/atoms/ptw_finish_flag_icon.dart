import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';

final class PtwFinishFlagIcon extends StatelessWidget {
  const PtwFinishFlagIcon({super.key, this.size = 20});

  final double size;

  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: const CustomPaint(painter: _FinishFlagPainter()),
  );
}

final class _FinishFlagPainter extends CustomPainter {
  const _FinishFlagPainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 20, size.height / 20);
    final white = Paint()..color = PtwColors.textOnAccent;
    final black = Paint()..color = PtwColors.ink;
    final outline =
        Paint()
          ..color = PtwColors.textOnAccent
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1;

    canvas.drawRect(const Rect.fromLTWH(2, 1, 2, 18), white);
    const left = 4.0;
    const top = 2.0;
    const cellWidth = 4.5;
    const cellHeight = 4.5;
    for (var row = 0; row < 2; row++) {
      for (var column = 0; column < 3; column++) {
        canvas.drawRect(
          Rect.fromLTWH(
            left + column * cellWidth,
            top + row * cellHeight,
            cellWidth,
            cellHeight,
          ),
          (row + column).isEven ? white : black,
        );
      }
    }
    canvas.drawRect(
      const Rect.fromLTWH(left, top, cellWidth * 3, cellHeight * 2),
      outline,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(_FinishFlagPainter oldDelegate) => false;
}
