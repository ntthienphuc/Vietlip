import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:lip_reader/src/data/history_repository.dart';
import 'package:lip_reader/src/data/settings_controller.dart';
import 'package:lip_reader/src/data/transcript_review.dart';
import 'package:lip_reader/src/features/result/result_screen.dart';
import 'package:lip_reader/src/models/reading_method.dart';
import 'package:lip_reader/src/models/transcript_rewrite.dart';
import 'package:lip_reader/src/models/transcription_result.dart';

TranscriptionResult original([String id = 'scene']) =>
    TranscriptionResult.fromJson({
      'request_id': id,
      'transcript': 'bản gốc từ môi',
      'model_id': 'SO17',
      'created_at': '2026-11-15T07:00:00Z',
      'diagnostics': {'video_path': '/local/video.mp4', 'source': 'realtime'},
    });

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test(
    'visual is the default; method persists and unknown modes migrate to visual',
    () async {
      final settings = SettingsController();
      await settings.load();
      expect(settings.readingMethod, ReadingMethod.visual);
      await settings.setReadingMethod(ReadingMethod.recovery);
      final reopened = SettingsController();
      await reopened.load();
      expect(reopened.readingMethod, ReadingMethod.recovery);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('vietlip_reading_method_v1', 'retired-model');
      await reopened.load();
      expect(reopened.readingMethod, ReadingMethod.visual);
    },
  );

  test(
    'AI saves raw before completion and changes only a separate field',
    () async {
      final settings = SettingsController();
      await settings.setReadingMethod(ReadingMethod.recovery);
      final history = HistoryRepository();
      final response = Completer<TranscriptRewrite>();
      ReadingMethod? requested;
      final saved = await saveWithReview(
        result: original(),
        settings: settings,
        history: history,
        rewrite: (raw, method) {
          expect(raw, 'bản gốc từ môi');
          requested = method;
          return response.future;
        },
      );
      expect(saved.rewrite!.pending, isTrue);
      expect((await history.list()).single.transcript, saved.transcript);
      await settings.setReadingMethod(ReadingMethod.visual);
      response.complete(
        const TranscriptRewrite(
          method: 'recovery',
          status: 'completed',
          text: 'một câu AI sửa',
        ),
      );
      await Future<void>.delayed(Duration.zero);
      final result = (await history.list()).single;
      expect(requested, ReadingMethod.recovery);
      expect(result.transcript, saved.transcript);
      expect(result.rewrite!.text, 'một câu AI sửa');
      expect(result.diagnostics, saved.diagnostics);
      expect(result.createdAt, saved.createdAt);
      expect(
        TranscriptionResult.fromJson(result.toJson()).rewrite!.text,
        result.rewrite!.text,
      );
    },
  );

  test('visual and empty captions never call AI', () async {
    final settings = SettingsController();
    final history = HistoryRepository();
    var calls = 0;
    Future<TranscriptRewrite> rewrite(String text, ReadingMethod method) async {
      calls++;
      throw StateError('Must not be called');
    }

    await saveWithReview(
      result: original(),
      settings: settings,
      history: history,
      rewrite: rewrite,
    );
    await settings.setReadingMethod(ReadingMethod.recovery);
    await saveWithReview(
      result: TranscriptionResult.fromJson({
        'request_id': 'silent',
        'transcript': '',
      }),
      settings: settings,
      history: history,
      rewrite: rewrite,
    );
    expect(calls, 0);
    expect((await history.list()).every((r) => r.rewrite == null), isTrue);
  });

  test(
    'AI error preserves raw caption and the original video reference',
    () async {
      final settings = SettingsController();
      await settings.setReadingMethod(ReadingMethod.recovery);
      final history = HistoryRepository();
      await saveWithReview(
        result: original(),
        settings: settings,
        history: history,
        rewrite: (_, _) async => throw TimeoutException('gateway unavailable'),
      );
      await Future<void>.delayed(Duration.zero);
      final result = (await history.list()).single;
      expect(result.transcript, 'bản gốc từ môi');
      expect(result.diagnostics['video_path'], '/local/video.mp4');
      expect(result.rewrite!.status, 'unavailable');
    },
  );

  test(
    'late AI completion cannot recreate history after it was cleared',
    () async {
      final settings = SettingsController();
      await settings.setReadingMethod(ReadingMethod.recovery);
      final history = HistoryRepository();
      final response = Completer<TranscriptRewrite>();
      await saveWithReview(
        result: original(),
        settings: settings,
        history: history,
        rewrite: (_, _) => response.future,
      );
      await history.clear();
      response.complete(
        const TranscriptRewrite(
          method: 'recovery',
          status: 'completed',
          text: 'late reply',
        ),
      );
      await Future<void>.delayed(Duration.zero);
      expect(await history.list(), isEmpty);
    },
  );

  test('late review and a newer recording are both retained', () async {
    final history = HistoryRepository();
    await history.add(original());
    await Future.wait([
      history.add(original('new-scene')),
      history.replaceIfPresent(
        original().withRewrite(
          const TranscriptRewrite(
            method: 'recovery',
            status: 'completed',
            text: 'AI result',
          ),
        ),
      ),
    ]);
    final rows = await history.list();
    expect(rows.map((r) => r.requestId), ['new-scene', 'scene']);
    expect(rows.last.rewrite!.text, 'AI result');
  });

  testWidgets('open result receives AI completion while keeping visible raw', (
    tester,
  ) async {
    final history = HistoryRepository();
    final pending = original().withRewrite(
      TranscriptRewrite(
        method: 'recovery',
        status: 'pending',
        startedAt: DateTime.now(),
      ),
    );
    await history.add(pending);
    await tester.pumpWidget(
      MaterialApp(
        home: ResultScreen(result: pending, history: history),
      ),
    );
    await tester.pump();
    expect(find.text('Phụ đề gốc'), findsOneWidget);
    expect(find.text('bản gốc từ môi'), findsOneWidget);
    await history.replaceIfPresent(
      original().withRewrite(
        const TranscriptRewrite(
          method: 'recovery',
          status: 'completed',
          text: 'bản sửa riêng',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('bản sửa riêng'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Gợi ý câu'), findsOneWidget);
    expect(find.text('bản sửa riêng'), findsOneWidget);
    expect(find.text('Sao chép gợi ý'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    history.dispose();
    expect(tester.takeException(), isNull);
  });

  testWidgets('expired pending state does not display an endless spinner', (
    tester,
  ) async {
    final result = original().withRewrite(
      TranscriptRewrite(
        method: 'recovery',
        status: 'pending',
        startedAt: DateTime.now().subtract(const Duration(minutes: 1)),
      ),
    );
    await tester.pumpWidget(MaterialApp(home: ResultScreen(result: result)));
    await tester.pumpAndSettle();
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
