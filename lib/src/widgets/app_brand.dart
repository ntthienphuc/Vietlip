import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

abstract final class AppBrand {
  static const name = 'VietLip';
  static const tagline = 'Đọc môi tiếng Việt';
}

/// The same simple speech mark is used by the launcher and capture header.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 40});
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: AppColors.primary,
      borderRadius: BorderRadius.circular(size * .3),
    ),
    child: Icon(Icons.subtitles_rounded, color: Colors.white, size: size * .6),
  );
}

class CaptureBrandHeader extends StatelessWidget {
  const CaptureBrandHeader({super.key});

  @override
  Widget build(BuildContext context) => const Row(
    children: [
      BrandMark(),
      SizedBox(width: 12),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              AppBrand.name,
              style: TextStyle(
                fontSize: 23,
                fontWeight: FontWeight.w700,
                letterSpacing: -.5,
              ),
            ),
            Text(
              AppBrand.tagline,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: AppColors.muted,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}
