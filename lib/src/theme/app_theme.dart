import 'package:flutter/material.dart';
import '../../shared/signova_style.dart';

abstract final class AppColors {
  static const ink = SignovaStyle.ink,
      muted = SignovaStyle.muted,
      canvas = SignovaStyle.canvas,
      surface = Colors.white,
      primary = SignovaStyle.blue,
      primarySoft = SignovaStyle.soft,
      accent = SignovaStyle.blue,
      caption = Colors.white,
      captionMuted = SignovaStyle.muted,
      success = SignovaStyle.green,
      warning = SignovaStyle.amber,
      warningSoft = Color(0xfffff0c4),
      error = SignovaStyle.red,
      border = SignovaStyle.line;
}

abstract final class AppTheme {
  static ThemeData get light => SignovaStyle.theme;
}
