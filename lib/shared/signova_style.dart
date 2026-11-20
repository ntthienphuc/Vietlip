import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Presentation tokens sampled from the local Signova learning interface.
/// Identical source is bundled in each independent app; no runtime dependency.
abstract final class SignovaStyle {
  static const ink = Color(0xff1e2742);
  static const muted = Color(0xff5f6f84);
  static const canvas = Color(0xfff5f8ff);
  static const sky = Color(0xff1cb0f6);
  static const blue = Color(0xff006b9a);
  static const soft = Color(0xffdff3ff);
  static const line = Color(0xffdce8f3);
  static const mint = Color(0xffdbffe9);
  static const green = Color(0xff237947);
  static const red = Color(0xffb9404b);
  static const amber = Color(0xff875716);

  static ThemeData get theme {
    final text = ThemeData.light().textTheme.apply(
      fontFamily: 'Nunito',
      bodyColor: ink,
      displayColor: ink,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: 'Nunito',
      colorScheme:
          ColorScheme.fromSeed(
            seedColor: sky,
            brightness: Brightness.light,
          ).copyWith(
            primary: blue,
            onPrimary: Colors.white,
            primaryContainer: soft,
            surface: Colors.white,
            onSurface: ink,
            error: red,
          ),
      scaffoldBackgroundColor: canvas,
      textTheme: text.copyWith(
        headlineSmall: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 26,
          fontWeight: FontWeight.w800,
          color: ink,
          height: 1.2,
        ),
        titleLarge: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 22,
          fontWeight: FontWeight.w800,
          color: ink,
        ),
        titleMedium: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: ink,
        ),
        bodyLarge: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 16,
          color: ink,
          height: 1.45,
        ),
        bodyMedium: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 14,
          color: ink,
          height: 1.45,
        ),
        bodySmall: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 13,
          color: muted,
          height: 1.4,
        ),
        labelLarge: const TextStyle(
          fontFamily: 'Nunito',
          fontSize: 15,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
      appBarTheme: const AppBarTheme(
        toolbarHeight: 72,
        backgroundColor: canvas,
        foregroundColor: ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: TextStyle(
          fontFamily: 'Nunito',
          fontSize: 24,
          fontWeight: FontWeight.w800,
          color: ink,
        ),
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: canvas,
          statusBarIconBrightness: Brightness.dark,
          systemNavigationBarColor: Colors.white,
          systemNavigationBarIconBrightness: Brightness.dark,
        ),
      ),
      iconTheme: const IconThemeData(color: blue, size: 22),
      dividerTheme: const DividerThemeData(color: line, space: 1),
      cardTheme: CardThemeData(
        color: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: line, width: 2),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style:
            FilledButton.styleFrom(
              minimumSize: const Size(48, 54),
              backgroundColor: sky,
              foregroundColor: ink,
              disabledBackgroundColor: line,
              disabledForegroundColor: muted,
              elevation: 3,
              shadowColor: const Color(0x661899d6),
              textStyle: const TextStyle(
                fontFamily: 'Nunito',
                fontSize: 16,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
            ).copyWith(
              animationDuration: const Duration(milliseconds: 140),
              elevation: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.disabled)) return 0;
                return states.contains(WidgetState.pressed) ? 1 : 3;
              }),
              overlayColor: WidgetStateProperty.resolveWith(
                (states) =>
                    states.contains(WidgetState.focused) ||
                        states.contains(WidgetState.pressed)
                    ? ink.withValues(alpha: .10)
                    : null,
              ),
              side: WidgetStateProperty.resolveWith(
                (states) => states.contains(WidgetState.focused)
                    ? const BorderSide(color: blue, width: 2)
                    : BorderSide.none,
              ),
            ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 50),
          foregroundColor: blue,
          side: const BorderSide(color: line, width: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Nunito',
            fontSize: 15,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(48, 48),
          foregroundColor: blue,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(minimumSize: const Size(48, 48)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.all(16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: line, width: 2),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: line, width: 2),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: blue, width: 2),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        indicatorColor: soft,
        height: 72,
        elevation: 0,
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected) ? blue : muted,
            size: 24,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (s) => TextStyle(
            fontFamily: 'Nunito',
            fontSize: 12,
            fontWeight: FontWeight.w800,
            color: s.contains(WidgetState.selected) ? blue : muted,
          ),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
      ),
      expansionTileTheme: const ExpansionTileThemeData(
        shape: Border(),
        collapsedShape: Border(),
        iconColor: blue,
        collapsedIconColor: muted,
      ),
      listTileTheme: const ListTileThemeData(iconColor: blue),
      textSelectionTheme: TextSelectionThemeData(
        cursorColor: blue,
        selectionColor: sky.withValues(alpha: .24),
        selectionHandleColor: blue,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: ink,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
    );
  }
}

class SignovaMascot extends StatelessWidget {
  const SignovaMascot({super.key, this.size = 44});
  final double size;
  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(14),
    child: Image.asset(
      'assets/signova/mascot.png',
      width: size,
      height: size,
      fit: BoxFit.contain,
      cacheWidth: 160,
      excludeFromSemantics: true,
    ),
  );
}

class SignovaHeader extends StatelessWidget {
  const SignovaHeader({super.key, required this.title, required this.subtitle});
  final String title, subtitle;
  @override
  Widget build(BuildContext context) => Semantics(
    header: true,
    child: Row(
      children: [
        const SignovaMascot(),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontFamily: 'Nunito',
                  fontSize: 23,
                  fontWeight: FontWeight.w800,
                  color: SignovaStyle.ink,
                  height: 1.15,
                ),
              ),
              if (MediaQuery.textScalerOf(context).scale(12) <= 16.5)
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontFamily: 'Nunito',
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: SignovaStyle.muted,
                    height: 1.4,
                  ),
                ),
            ],
          ),
        ),
      ],
    ),
  );
}

/// The same tactile surface around results and task cards in all three apps.
class SignovaPanel extends StatelessWidget {
  const SignovaPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });
  final Widget child;
  final EdgeInsetsGeometry padding;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: padding,
    decoration: BoxDecoration(
      color: Colors.white,
      border: Border.all(color: SignovaStyle.line, width: 2),
      borderRadius: BorderRadius.circular(24),
      boxShadow: const [
        BoxShadow(color: SignovaStyle.line, offset: Offset(0, 3)),
      ],
    ),
    child: Material(color: Colors.transparent, child: child),
  );
}

class SignovaIconBadge extends StatelessWidget {
  const SignovaIconBadge(
    this.icon, {
    super.key,
    this.size = 32,
    this.color = SignovaStyle.blue,
    this.background = SignovaStyle.soft,
  });
  final IconData icon;
  final double size;
  final Color color, background;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(size * .36),
      ),
      child: Icon(icon, color: color, size: size * .57),
    ),
  );
}
