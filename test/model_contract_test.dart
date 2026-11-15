import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:lip_reader/src/data/camera_frame_encoder.dart';
import 'package:lip_reader/src/data/live_lip_session.dart';
import 'package:lip_reader/src/data/lip_reader_api.dart';
import 'package:lip_reader/src/features/result/result_screen.dart';
import 'package:lip_reader/src/models/transcription_result.dart';

void main() {
  test('derives secure and local realtime websocket endpoints', () {
    expect(
      LiveLipSession.realtimeEndpoint('http://192.168.1.20:7100').toString(),
      'ws://192.168.1.20:7100/v1/realtime',
    );
    expect(
      LiveLipSession.realtimeEndpoint('https://lip.example/api').toString(),
      'wss://lip.example/v1/realtime',
    );
  });

  test('encodes a BGRA camera frame into a valid JPEG', () {
    final jpeg = encodeCameraFrame({
      'width': 2,
      'height': 2,
      'rotation': 0,
      'format': 'bgra8888',
      'planes': [
        {
          'bytes': Uint8List.fromList([
            0,
            0,
            255,
            255,
            0,
            255,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            255,
            255,
            255,
          ]),
          'rowStride': 8,
          'pixelStride': 4,
        },
      ],
    });

    expect(jpeg, isNotNull);
    final decoded = img.decodeJpg(jpeg!);
    expect(decoded?.width, 2);
    expect(decoded?.height, 2);
  });

  test('parses the review-only API contract', () {
    final result = TranscriptionResult.fromJson({
      'request_id': 'request-1',
      'transcript': 'xin chào',
      'status': 'review_required',
      'model_id': 'auto-avsr-test',
      'elapsed_ms': 1250,
      'num_frames': 50,
      'created_at': '2026-07-24T00:00:00Z',
      'alternatives': [
        {'text': 'xin chào', 'raw_score': -1.0},
        {'text': 'xin chao', 'raw_score': -2.0},
      ],
      'processing_mode': 'llm_assist',
      'assisted_transcript': 'xin chào bạn',
      'consensus_transcript': 'xin chào',
      'risk_notice': 'LLM có thể suy đoán.',
      'diagnostics': {'context_hint_applied': false},
    });

    expect(result.status, 'review_required');
    expect(result.transcript, 'xin chào');
    expect(result.alternatives, hasLength(2));
    expect(result.diagnostics['context_hint_applied'], isFalse);
    expect(result.processingMode, 'llm_assist');
    expect(result.assistedTranscript, 'xin chào bạn');
    expect(result.consensusTranscript, 'xin chào');
  });

  test('round-trips local history JSON', () {
    final now = DateTime.utc(2026, 7, 24);
    final original = TranscriptionResult(
      requestId: 'request-2',
      transcript: 'cảm ơn',
      status: 'review_required',
      modelId: 'auto-avsr-test',
      elapsedMs: 900,
      numFrames: 40,
      createdAt: now,
      alternatives: const [],
      diagnostics: const {'warnings': <String>[]},
    );

    final restored = TranscriptionResult.fromJson(original.toJson());
    expect(restored.requestId, original.requestId);
    expect(restored.createdAt, now);
    expect(restored.transcript, 'cảm ơn');
  });

  test('turns a receive timeout into a Vietnamese action message', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/v1/transcriptions'),
      type: DioExceptionType.receiveTimeout,
    );

    expect(
      LipReaderApi.readableError(error),
      contains('Máy chủ xử lý quá lâu'),
    );
  });

  testWidgets('legacy history shows only the original visual transcript', (
    tester,
  ) async {
    final result = TranscriptionResult.fromJson({
      'request_id': 'legacy',
      'transcript': 'xin chào',
      'processing_mode': 'llm_assist',
      'assisted_transcript': 'Một câu khác do trợ lý viết lại.',
      'diagnostics': {
        'llm': {'provider': 'ollama', 'model': 'legacy-model'},
      },
    });
    await tester.pumpWidget(MaterialApp(home: ResultScreen(result: result)));
    expect(find.text('xin chào'), findsOneWidget);
    expect(find.textContaining('trợ lý viết lại'), findsNothing);
    expect(find.textContaining('LLM'), findsNothing);
    expect(find.textContaining('legacy-model'), findsNothing);
    expect(
      result.toJson()['assisted_transcript'],
      'Một câu khác do trợ lý viết lại.',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('session duration is distinguished from batch processing time', (
    tester,
  ) async {
    final result = TranscriptionResult.fromJson({
      'request_id': 'live-duration',
      'transcript': 'cảm ơn bạn',
      'elapsed_ms': 51000,
      'diagnostics': {'source': 'realtime'},
    });
    await tester.pumpWidget(MaterialApp(home: ResultScreen(result: result)));
    await tester.ensureVisible(find.text('Thông tin phiên'));
    await tester.tap(find.text('Thông tin phiên'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Thời lượng phiên: 51.00 giây'), findsOneWidget);
    expect(find.textContaining('Thời gian xử lý:'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
