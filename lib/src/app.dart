import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'data/history_repository.dart';
import 'data/settings_controller.dart';
import 'features/capture/capture_screen.dart';
import 'features/history/history_screen.dart';
import 'features/result/result_screen.dart';
import 'features/settings/settings_screen.dart';
import 'models/transcription_result.dart';
import 'theme/app_theme.dart';
import 'widgets/app_shell.dart';

class LipReaderApp extends StatefulWidget {
  const LipReaderApp({
    required this.settings,
    required this.history,
    super.key,
  });

  final SettingsController settings;
  final HistoryRepository history;

  @override
  State<LipReaderApp> createState() => _LipReaderAppState();
}

class _LipReaderAppState extends State<LipReaderApp> {
  late final GoRouter _router = GoRouter(
    initialLocation: '/read',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/read',
                builder: (context, state) => CaptureScreen(
                  settings: widget.settings,
                  history: widget.history,
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/history',
                builder: (context, state) =>
                    HistoryScreen(history: widget.history),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/settings',
                builder: (context, state) =>
                    SettingsScreen(settings: widget.settings),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/result',
        builder: (context, state) {
          final result = state.extra;
          if (result is! TranscriptionResult) {
            return const Scaffold(
              body: Center(child: Text('Không tìm thấy kết quả.')),
            );
          }
          return ResultScreen(result: result);
        },
      ),
    ],
  );

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'LipLens',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: _router,
    );
  }
}
