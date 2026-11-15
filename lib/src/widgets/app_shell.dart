import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';

class AppShell extends StatefulWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  bool _capturing = false;

  @override
  Widget build(BuildContext context) {
    final navigationShell = widget.navigationShell;
    return Scaffold(
      body: NotificationListener<CaptureSessionNotification>(
        onNotification: (notification) {
          if (_capturing != notification.active) {
            setState(() => _capturing = notification.active);
          }
          return true;
        },
        child: CaptureVisibility(
          active: navigationShell.currentIndex == 0,
          child: navigationShell,
        ),
      ),
      bottomNavigationBar: _capturing && navigationShell.currentIndex == 0
          ? null
          : DecoratedBox(
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: NavigationBar(
                selectedIndex: navigationShell.currentIndex,
                onDestinationSelected: (index) => navigationShell.goBranch(
                  index,
                  initialLocation: index == navigationShell.currentIndex,
                ),
                destinations: const [
                  NavigationDestination(
                    icon: Icon(Icons.center_focus_weak_rounded),
                    selectedIcon: Icon(Icons.center_focus_strong_rounded),
                    label: 'Đọc môi',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.history_outlined),
                    selectedIcon: Icon(Icons.history),
                    label: 'Lịch sử',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.tune_outlined),
                    selectedIcon: Icon(Icons.tune),
                    label: 'Cài đặt',
                  ),
                ],
              ),
            ),
    );
  }
}

class CaptureSessionNotification extends Notification {
  const CaptureSessionNotification(this.active);
  final bool active;
}

class CaptureVisibility extends InheritedWidget {
  const CaptureVisibility({
    required this.active,
    required super.child,
    super.key,
  });
  final bool active;
  static bool of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<CaptureVisibility>()?.active ??
      true;
  @override
  bool updateShouldNotify(CaptureVisibility oldWidget) =>
      active != oldWidget.active;
}
