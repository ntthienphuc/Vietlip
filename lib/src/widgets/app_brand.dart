import 'package:flutter/material.dart';

import '../../shared/signova_style.dart';

abstract final class AppBrand {
  static const name = 'VietLip';
  static const tagline = 'Nhìn khẩu hình, đọc lời nói';
}

class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 40});
  final double size;
  @override
  Widget build(BuildContext context) => SignovaMascot(size: size);
}

class CaptureBrandHeader extends StatelessWidget {
  const CaptureBrandHeader({super.key});
  @override
  Widget build(BuildContext context) =>
      const SignovaHeader(title: AppBrand.name, subtitle: AppBrand.tagline);
}
