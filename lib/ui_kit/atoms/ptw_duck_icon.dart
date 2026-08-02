import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';

final class PtwDuckIcon extends StatelessWidget {
  const PtwDuckIcon({
    super.key,
    this.size = 18,
    this.color = PtwColors.textOnAccent,
  });

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: CustomPaint(painter: _DuckOutlinePainter(color)),
  );
}

final class _DuckOutlinePainter extends CustomPainter {
  const _DuckOutlinePainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 24, size.height / 24);

    var silhouette = Path()..addOval(const Rect.fromLTWH(2, 10, 16, 10));
    silhouette = Path.combine(
      PathOperation.union,
      silhouette,
      Path()..addOval(const Rect.fromLTWH(12, 3, 9, 9)),
    );
    silhouette = Path.combine(
      PathOperation.union,
      silhouette,
      Path()
        ..moveTo(20, 6.5)
        ..lineTo(23, 8.5)
        ..lineTo(20, 10)
        ..close(),
    );
    silhouette = Path.combine(
      PathOperation.union,
      silhouette,
      Path()
        ..moveTo(3.5, 12)
        ..lineTo(0.8, 9.5)
        ..lineTo(1.4, 15)
        ..close(),
    );

    final stroke =
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeCap = StrokeCap.round
          ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(silhouette, stroke);
    canvas.drawPath(
      Path()
        ..moveTo(6, 14)
        ..quadraticBezierTo(10, 11.5, 14, 15),
      stroke,
    );
    canvas.drawCircle(const Offset(17.5, 6.5), 0.9, Paint()..color = color);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_DuckOutlinePainter oldDelegate) =>
      oldDelegate.color != color;
}
