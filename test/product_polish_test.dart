import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/settings_controller.dart';
import 'package:lip_reader/src/data/history_repository.dart';
import 'package:lip_reader/src/features/capture/capture_screen.dart';
import 'package:lip_reader/src/features/capture/live_caption_panel.dart';
import 'package:lip_reader/src/features/capture/server_connection_banner.dart';
import 'package:lip_reader/src/features/history/history_screen.dart';
import 'package:lip_reader/src/features/settings/settings_screen.dart';
import 'package:lip_reader/src/features/result/result_screen.dart';
import 'package:lip_reader/src/models/transcription_result.dart';
import 'package:lip_reader/src/theme/app_theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
    'saved address is not readiness and stale responses are ignored',
    (tester) async {
      final settings = SettingsController();
      await settings.setApiUrl('192.168.1.20');
      final first = Completer<Map<String, dynamic>>();
      var calls = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ServerConnectionBanner(
              settings: settings,
              active: true,
              onConfigure: () {},
              loadHealth: () => calls++ == 0
                  ? first.future
                  : Future.value({'realtime_available': false}),
            ),
          ),
        ),
      );
      expect(find.text('Đang kiểm tra máy chủ…'), findsOneWidget);
      expect(find.text('Máy chủ sẵn sàng'), findsNothing);
      await settings.setApiUrl('192.168.1.21');
      await tester.pump();
      first.complete({'realtime_available': true});
      await tester.pumpAndSettle();
      expect(find.text('Máy chủ đang chuẩn bị'), findsOneWidget);
      expect(find.text('Máy chủ sẵn sàng'), findsNothing);
      expect(find.text('192.168.1.21:7100'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      settings.dispose();
    },
  );

  testWidgets(
    'address validation stays at the input and keeps unsaved history',
    (tester) async {
      final settings = SettingsController();
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: SettingsScreen(settings: settings),
        ),
      );
      await tester.enterText(find.byType(TextField), 'ftp://invalid');
      await tester.tap(find.text('Lưu và kiểm tra'));
      await tester.pumpAndSettle();
      expect(
        find.text('Nhập IP hoặc địa chỉ http:// của máy chủ.'),
        findsOneWidget,
      );
      expect(settings.apiUrl, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      settings.dispose();
    },
  );

  testWidgets(
    'settings and long results fit phone/tablet widths with large text',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final settings = SettingsController();
      final result = TranscriptionResult.fromJson({
        'request_id': 'layout',
        'transcript': List.filled(80, 'Xin chào mọi người.').join(' '),
        'diagnostics': {'source': 'realtime'},
      });
      for (final size in [
        const Size(360, 640),
        const Size(412, 846),
        const Size(800, 1024),
      ]) {
        for (final scale in [1.0, 2.0]) {
          tester.view.physicalSize = size;
          for (final screen in [
            SettingsScreen(settings: settings),
            ResultScreen(result: result),
          ]) {
            await tester.pumpWidget(
              MaterialApp(
                theme: AppTheme.light,
                home: MediaQuery(
                  data: MediaQueryData(
                    size: size,
                    textScaler: TextScaler.linear(scale),
                  ),
                  child: screen,
                ),
              ),
            );
            await tester.pumpAndSettle();
            expect(
              tester.takeException(),
              isNull,
              reason: '$size / $scale / ${screen.runtimeType}',
            );
          }
        }
      }
      await tester.pumpWidget(const SizedBox());
      settings.dispose();
    },
  );

  testWidgets(
    'initial camera layout shows captions and keeps controls visible at large text',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final settings = SettingsController();
      final history = HistoryRepository();
      for (final size in [const Size(360, 640), const Size(412, 846)]) {
        for (final scale in [1.0, 2.0]) {
          tester.view.physicalSize = size;
          await tester.pumpWidget(
            MaterialApp(
              theme: AppTheme.light,
              home: MediaQuery(
                data: MediaQueryData(
                  size: size,
                  textScaler: TextScaler.linear(scale),
                ),
                child: CaptureScreen(settings: settings, history: history),
              ),
            ),
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 100));
          expect(tester.takeException(), isNull, reason: '$size / $scale');
          expect(find.text('Kết nối máy tính'), findsOneWidget);
          expect(find.byType(LiveCaptionPanel), findsOneWidget);
          expect(
            tester.widget<LiveCaptionPanel>(find.byType(LiveCaptionPanel)).idle,
            isTrue,
          );
          final rect = tester.getRect(
            find.widgetWithText(FilledButton, 'Kết nối máy tính'),
          );
          expect(rect.bottom, lessThanOrEqualTo(size.height));
          expect(rect.top, greaterThan(0));
          if (scale == 1.0) {
            final captionRect = tester.getRect(find.byType(LiveCaptionPanel));
            expect(captionRect.top, greaterThan(0));
            expect(captionRect.bottom, lessThan(rect.top));
          }
        }
      }
      await tester.pumpWidget(const SizedBox());
      settings.dispose();
      history.dispose();
    },
  );

  testWidgets('failed history can be retried instead of spinning forever', (
    tester,
  ) async {
    final history = _RetryHistory();
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: HistoryScreen(history: history),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Chưa mở được lịch sử'), findsOneWidget);
    await tester.tap(find.text('Tải lại lịch sử'));
    await tester.pumpAndSettle();
    expect(find.text('Chưa có bản đọc môi nào'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    history.dispose();
  });
}

class _RetryHistory extends HistoryRepository {
  int attempts = 0;
  @override
  Future<List<TranscriptionResult>> list() async {
    if (attempts++ == 0) throw StateError('fixture');
    return [];
  }
}
