import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/live_lip_session.dart';
import 'package:lip_reader/src/data/live_sentence_recovery.dart';
import 'package:lip_reader/src/features/capture/live_capture_layout.dart';
import 'package:lip_reader/src/features/capture/sentence_caption_panel.dart';
import 'package:lip_reader/src/models/reading_method.dart';
import 'package:lip_reader/src/models/transcript_rewrite.dart';
import 'package:lip_reader/src/models/transcription_result.dart';

LiveLipUpdate packet(String type, String text, [int? turn]) => LiveLipUpdate(
  type: type,
  transcript: text,
  stableTranscript: text,
  turnId: turn,
);
TranscriptRewrite response(String id, String text) => TranscriptRewrite(
  method: 'recovery',
  provider: 'groq',
  sentenceId: id,
  status: 'completed',
  text: text,
);

void main() {
  test(
    'AI sees one whole endpoint, never partial windows or repeated final packets',
    () async {
      final calls = <String>[];
      final recovery = LiveSentenceRecovery(
        sessionId: 'live',
        method: ReadingMethod.recovery,
        provider: AiProvider.groq,
        call: (text, id) async {
          calls.add(text);
          return response(id, text);
        },
      );
      recovery.accept(packet('partial', 'xin'));
      recovery.accept(packet('partial', 'xin chào'));
      expect(calls, isEmpty);
      recovery.accept(packet('segment_final', 'xin chào', 1));
      recovery.accept(packet('segment_final', 'xin chào', 1));
      recovery.accept(packet('session_final', 'xin chào'));
      await recovery.settled;
      expect(calls, ['xin chào']);
      recovery.accept(packet('partial', 'xin chào xin'));
      expect(recovery.draft, 'xin');
      recovery.accept(packet('segment_final', 'xin chào xin chào', 2));
      await recovery.settled;
      expect(calls, ['xin chào', 'xin chào']);
      expect(recovery.sentences.map((s) => s.id), ['live-1', 'live-2']);
      recovery.dispose();
    },
  );

  test(
    'late and out-of-order AI replies remain paired with their own raw sentence',
    () async {
      final replies = <String, Completer<TranscriptRewrite>>{};
      final recovery = LiveSentenceRecovery(
        sessionId: 'live',
        method: ReadingMethod.recovery,
        provider: AiProvider.groq,
        call: (text, id) =>
            (replies[id] = Completer<TranscriptRewrite>()).future,
      );
      recovery.accept(packet('segment_final', 'câu thứ nhất', 1));
      recovery.accept(packet('partial', 'câu thứ nhất câu thứ'));
      recovery.accept(packet('segment_final', 'câu thứ nhất câu thứ hai', 2));
      recovery.accept(packet('partial', 'câu thứ nhất câu thứ hai đang nói'));
      replies['live-2']!.complete(response('live-2', 'AI hai'));
      await Future<void>.delayed(Duration.zero);
      expect(recovery.sentences[0].pending, isTrue);
      expect(recovery.sentences[1].raw, 'câu thứ hai');
      expect(recovery.sentences[1].rewrite!.text, 'AI hai');
      expect(recovery.draft, 'đang nói');
      replies['live-1']!.complete(response('live-1', 'AI một'));
      await recovery.settled;
      expect(recovery.sentences.map((s) => s.rewrite!.text), [
        'AI một',
        'AI hai',
      ]);
      expect(recovery.sentences.map((s) => s.raw), [
        'câu thứ nhất',
        'câu thứ hai',
      ]);
      recovery.dispose();
    },
  );

  test(
    'silence, stale packets and direct mode never trigger an extra AI request',
    () async {
      var calls = 0;
      final recovery = LiveSentenceRecovery(
        sessionId: 'live',
        method: ReadingMethod.visual,
        provider: AiProvider.groq,
        call: (_, _) async {
          calls++;
          throw StateError('must not call');
        },
      );
      recovery.accept(packet('segment_final', '', 1));
      recovery.accept(packet('segment_final', 'câu một', 2));
      recovery.accept(packet('partial', 'câu'));
      recovery.accept(packet('session_final', 'câu một'));
      expect(calls, 0);
      expect(recovery.sentences.single.raw, 'câu một');
      expect(recovery.sentences.single.rewrite, isNull);
      recovery.dispose();
    },
  );

  test(
    'wrong reply ID and timeout preserve source and end the loading state',
    () async {
      final late = Completer<TranscriptRewrite>();
      var count = 0;
      final recovery = LiveSentenceRecovery(
        sessionId: 'live',
        method: ReadingMethod.recovery,
        provider: AiProvider.groq,
        timeout: const Duration(milliseconds: 10),
        call: (_, id) {
          count++;
          return count == 1
              ? Future.value(response('other-id', 'wrong'))
              : late.future;
        },
      );
      recovery.accept(packet('segment_final', 'một', 1));
      recovery.accept(packet('segment_final', 'một hai', 2));
      await recovery.settled;
      expect(recovery.pendingCount, 0);
      expect(
        recovery.sentences.every((s) => s.rewrite!.status == 'unavailable'),
        isTrue,
      );
      late.complete(response('live-2', 'late'));
      await Future<void>.delayed(Duration.zero);
      expect(recovery.sentences[1].rewrite!.hasText, isFalse);
      expect(recovery.sentences.map((s) => s.raw), ['một', 'hai']);
      final saved = TranscriptionResult.fromJson({
        'request_id': 'live',
        'transcript': 'một hai',
      }).withSentences(recovery.sentences);
      final reopened = TranscriptionResult.fromJson(saved.toJson());
      expect(reopened.sentences[1].raw, 'hai');
      expect(reopened.sentences[1].rewrite!.provider, 'groq');
      recovery.dispose();
    },
  );

  testWidgets('paired captions remain readable at small and large text sizes', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final recovery = LiveSentenceRecovery(
      sessionId: 'live',
      method: ReadingMethod.recovery,
      provider: AiProvider.groq,
      call: (_, id) async => response(id, 'Bạn có thể giúp tôi được không?'),
    );
    recovery.accept(
      packet('segment_final', 'bạn có thể giúp tôi được không', 1),
    );
    await recovery.settled;
    for (final size in [
      const Size(360, 640),
      const Size(412, 780),
      const Size(800, 720),
    ]) {
      for (final scale in [1.0, 1.6, 2.0]) {
        tester.view.physicalSize = size;
        await tester.pumpWidget(
          MaterialApp(
            home: MediaQuery(
              data: MediaQueryData(
                size: size,
                textScaler: TextScaler.linear(scale),
              ),
              child: Scaffold(
                body: LiveCaptureLayout(
                  recovery: true,
                  header: const Text('Khôi phục câu'),
                  preview: const ColoredBox(color: Colors.black),
                  controls: FilledButton(
                    onPressed: () {},
                    child: const Text('Kết thúc phiên'),
                  ),
                  captions: SentenceCaptionPanel(
                    sentences: recovery.sentences,
                    draft: '',
                    provider: AiProvider.groq,
                    status: 'Sẵn sàng',
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$size / $scale');
        expect(find.text('AI KHÔI PHỤC'), findsOneWidget);
        expect(find.text('Bạn có thể giúp tôi được không?'), findsOneWidget);
      }
    }
    await tester.pumpWidget(const SizedBox());
    recovery.dispose();
  });
}
