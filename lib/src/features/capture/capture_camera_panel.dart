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
    borderRadius: BorderRadius.circular(24),
    child: ColoredBox(
      color: const Color(0xFF111A1C),
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
                      Icons.circle,
                      size: 7,
                      color: recording
                          ? const Color(0xFFFF8276)
                          : AppColors.primarySoft,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      recording ? timerLabel : 'Giữ rõ khuôn mặt',
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
    final width = size.width * .72;
    final height = (width * 1.35).clamp(0.0, size.height * .72);
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * .46),
      width: width,
      height: height,
    );
    final guide = RRect.fromRectAndRadius(rect, Radius.circular(width / 2));
    canvas.drawRRect(
      guide,
      Paint()
        ..color = Colors.white.withValues(alpha: .65)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
  }

  @override
  bool shouldRepaint(covariant FaceGuidePainter oldDelegate) => false;
}
