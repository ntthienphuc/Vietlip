import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// Camera chrome is independent of capture/transport state.
class CaptureCameraPanel extends StatelessWidget {
  const CaptureCameraPanel({
    super.key,
    required this.preview,
    required this.recording,
    required this.timerLabel,
    this.onFlip,
  });

  final Widget preview;
  final bool recording;
  final String timerLabel;
  final VoidCallback? onFlip;

  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(26),
    child: ColoredBox(
      color: AppColors.caption,
      child: Stack(
        fit: StackFit.expand,
        children: [
          preview,
          Positioned(
            top: 14,
            left: 14,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: .55),
                borderRadius: BorderRadius.circular(30),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      recording ? Icons.circle : Icons.face_retouching_natural,
                      size: recording ? 7 : 15,
                      color: recording ? const Color(0xFFFF8276) : Colors.white,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      recording ? timerLabel : 'Đặt môi trong khung',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (!recording && onFlip != null)
            Positioned(
              top: 7,
              right: 7,
              child: IconButton.filledTonal(
                tooltip: 'Đổi camera',
                onPressed: onFlip,
                style: IconButton.styleFrom(
                  backgroundColor: Colors.black.withValues(alpha: .55),
                  foregroundColor: Colors.white,
                ),
                icon: const Icon(Icons.cameraswitch_outlined, size: 21),
              ),
            ),
        ],
      ),
    ),
  );
}

/// Drawn inside the fitted image so the guide follows its actual aspect ratio.
class FaceGuidePainter extends CustomPainter {
  const FaceGuidePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final width = (size.width * .65).clamp(0.0, size.height * .68 / 1.35);
    final height = width * 1.35;
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * .51),
      width: width,
      height: height,
    );
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: .85)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 2;
    const length = 25.0, radius = 18.0;
    for (final corner in [
      (rect.left, rect.top, 1.0, 1.0),
      (rect.right, rect.top, -1.0, 1.0),
      (rect.left, rect.bottom, 1.0, -1.0),
      (rect.right, rect.bottom, -1.0, -1.0),
    ]) {
      final (x, y, dx, dy) = corner;
      canvas.drawPath(
        Path()
          ..moveTo(x, y + dy * length)
          ..lineTo(x, y + dy * radius)
          ..quadraticBezierTo(x, y, x + dx * radius, y)
          ..lineTo(x + dx * length, y),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant FaceGuidePainter oldDelegate) => false;
}
