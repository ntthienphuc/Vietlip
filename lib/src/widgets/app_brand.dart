import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

abstract final class AppBrand {
  static const name = 'VietLip';
  static const tagline = 'Nhìn khẩu hình, đọc lời nói';
}

/// Two lip contours form the product mark. No image or network dependency.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 40});
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    padding: EdgeInsets.all(size * .19),
    decoration: BoxDecoration(
      color: AppColors.primary,
      borderRadius: BorderRadius.circular(size * .34),
    ),
    child: const CustomPaint(painter: _LipMarkPainter()),
  );
}

class _LipMarkPainter extends CustomPainter {
  const _LipMarkPainter();
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = size.width * .09
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;
    final w = size.width, h = size.height;
    canvas.drawPath(
      Path()
        ..moveTo(w * .06, h * .53)
        ..cubicTo(w * .25, h * .48, w * .30, h * .17, w * .5, h * .33)
        ..cubicTo(w * .70, h * .17, w * .75, h * .48, w * .94, h * .53)
        ..cubicTo(w * .72, h * .92, w * .28, h * .92, w * .06, h * .53),
      paint,
    );
    canvas.drawPath(
      Path()
        ..moveTo(w * .13, h * .54)
        ..quadraticBezierTo(w * .5, h * .64, w * .87, h * .54),
      paint,
    );
  }

  @override
  bool shouldRepaint(_LipMarkPainter oldDelegate) => false;
}

class CaptureBrandHeader extends StatelessWidget {
  const CaptureBrandHeader({super.key});
  @override
  Widget build(BuildContext context) => const Row(
    children: [
      BrandMark(size: 42),
      SizedBox(width: 12),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              AppBrand.name,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                letterSpacing: -1,
              ),
            ),
            SizedBox(height: 1),
            Text(
              AppBrand.tagline,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 11, color: AppColors.muted),
            ),
          ],
        ),
      ),
    ],
  );
}
