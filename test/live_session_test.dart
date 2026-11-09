import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/live_lip_session.dart';

void main() {
  test(
    'caption frame receipt echoes its ID after delivery without sending text',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      WebSocket? peer;
      final received = Completer<Map<String, dynamic>>();
      final listener = server.listen((request) async {
        peer = await WebSocketTransformer.upgrade(request);
        peer!.listen((event) {
          final control = jsonDecode(event as String) as Map<String, dynamic>;
          if (control['type'] == 'start') {
            peer!.add(jsonEncode({'type': 'ready', 'protocol': 2}));
          } else if (control['type'] == 'caption_rendered') {
            received.complete(control);
          }
        });
      });
      final session = LiveLipSession('http://127.0.0.1:${server.port}');
      try {
        await session.connect();
        final next = session.updates.firstWhere(
          (event) => event.type == 'segment_final',
        );
        peer!.add(
          jsonEncode({
            'type': 'segment_final',
            'caption_event_id': 7,
            'transcript': 'xin chào',
            'stable_transcript': 'xin chào',
          }),
        );
        final update = await next.timeout(const Duration(seconds: 2));
        await Future<void>.delayed(const Duration(milliseconds: 20));
        session.acknowledgeCaptionFrame(update);
        final receipt = await received.future.timeout(
          const Duration(seconds: 2),
        );
        expect(receipt['caption_event_id'], 7);
        expect(receipt['receive_to_frame_ms'], greaterThanOrEqualTo(15));
        expect(receipt.containsKey('transcript'), isFalse);
        expect(session.rejectedTimestampFrames, 0);
      } finally {
        await session.dispose();
        await peer?.close();
        await listener.cancel();
        await server.close(force: true);
      }
    },
  );

  test(
    'a server rejection fails immediately instead of waiting for ready',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      WebSocket? peer;
      final listener = server.listen((request) async {
        peer = await WebSocketTransformer.upgrade(request);
        peer!.listen((event) {
          peer!.add(
            jsonEncode({
              'type': 'error',
              'code': 'model_unavailable',
              'message': 'Mô hình chưa sẵn sàng.',
            }),
          );
        });
      });
      final session = LiveLipSession('http://127.0.0.1:${server.port}');
      final clock = Stopwatch()..start();
      try {
        await expectLater(session.connect(), throwsA(isA<StateError>()));
        expect(clock.elapsed, lessThan(const Duration(seconds: 2)));
        expect(session.isConnected, isFalse);
      } finally {
        await session.dispose();
        await peer?.close();
        await listener.cancel();
        await server.close(force: true);
      }
    },
  );

  test(
    'connected socket without ready obeys the whole-start deadline',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      WebSocket? peer;
      final listener = server.listen((request) async {
        peer = await WebSocketTransformer.upgrade(request);
        peer!.listen((_) {});
      });
      final stages = <String>[];
      final session = LiveLipSession(
        'http://127.0.0.1:${server.port}',
        connectTimeout: const Duration(milliseconds: 250),
        onConnectionStage: stages.add,
      );
      final clock = Stopwatch()..start();
      try {
        await expectLater(session.connect(), throwsA(isA<TimeoutException>()));
        expect(clock.elapsed, lessThan(const Duration(seconds: 2)));
        expect(stages.length, 2);
        expect(session.isConnected, isFalse);
      } finally {
        await session.dispose();
        await peer?.close();
        await listener.cancel();
        await server.close(force: true);
      }
    },
  );

  test(
    'repeated sessions reset time and discard stale frames without spending credits',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final peers = <WebSocket>[];
      final seen = <List<List<num>>>[];
      final listener = server.listen((request) async {
        final peer = await WebSocketTransformer.upgrade(request);
        peers.add(peer);
        final frames = <List<num>>[];
        seen.add(frames);
        peer.listen((event) {
          if (event is String) {
            final control = jsonDecode(event) as Map<String, dynamic>;
            if (control['type'] == 'start') {
              peer.add(
                jsonEncode({
                  'type': 'ready',
                  'protocol': 2,
                  'sample_fps': 25,
                  'max_inflight_frames': 4,
                  'auto_endpoint': true,
                }),
              );
            } else if (control['type'] == 'stop') {
              peer.add(
                jsonEncode({'type': 'session_final', 'transcript': 'xin chào'}),
              );
            }
          } else {
            final header = ByteData.sublistView(
              Uint8List.fromList(event as List<int>),
            );
            frames.add([
              header.getUint32(4, Endian.big),
              header.getFloat64(8, Endian.big),
            ]);
          }
        });
      });
      try {
        for (var round = 0; round < 4; round++) {
          final session = LiveLipSession('http://127.0.0.1:${server.port}');
          try {
            await session.connect();
            final jpeg = Uint8List.fromList([255, 216, 255, 217]);
            for (final time in [0.0, 40.0]) {
              expect(session.sendFrame(jpeg, capturedAtMs: time), isTrue);
            }
            for (final stale in [-1.0, 0.0, 40.0]) {
              expect(session.sendFrame(jpeg, capturedAtMs: stale), isFalse);
            }
            for (final time in [80.0, 120.0]) {
              expect(session.sendFrame(jpeg, capturedAtMs: time), isTrue);
            }
            expect(session.rejectedTimestampFrames, 3);
            expect(await session.stop(), 'xin chào');
          } finally {
            await session.dispose();
          }
        }
        expect(seen.length, 4);
        for (final frames in seen) {
          expect(frames, [
            [0, 0.0],
            [1, 40.0],
            [2, 80.0],
            [3, 120.0],
          ]);
        }
      } finally {
        for (final peer in peers) {
          await peer.close();
        }
        await listener.cancel();
        await server.close(force: true);
      }
    },
  );

  test(
    'fatal frame error after ready stops sending and preserves the error state',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      WebSocket? peer;
      final listener = server.listen((request) async {
        peer = await WebSocketTransformer.upgrade(request);
        peer!.listen((event) {
          if (event is String) {
            peer!.add(jsonEncode({'type': 'ready', 'protocol': 2}));
          } else {
            peer!.add(
              jsonEncode({
                'type': 'error',
                'code': 'invalid_frame',
                'message': 'Invalid timestamps',
              }),
            );
          }
        });
      });
      final session = LiveLipSession('http://127.0.0.1:${server.port}');
      final failure = session.updates.firstWhere((e) => e.type == 'error');
      try {
        await session.connect();
        session.sendFrame(
          Uint8List.fromList([255, 216, 255, 217]),
          capturedAtMs: 0,
        );
        final event = await failure.timeout(const Duration(seconds: 2));
        expect(event.recognitionState, 'disconnected');
        expect(event.message, contains('Luồng hình bị lỗi'));
        expect(session.canSendFrame, isFalse);
        expect(await session.stop(), isNull);
      } finally {
        await session.dispose();
        await peer?.close();
        await listener.cancel();
        await server.close(force: true);
      }
    },
  );

  test('a peer that never upgrades cannot trap connection cleanup', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final listener = server.listen((request) {});
    final session = LiveLipSession(
      'http://127.0.0.1:${server.port}',
      connectTimeout: const Duration(milliseconds: 150),
    );
    final clock = Stopwatch()..start();
    try {
      await expectLater(session.connect(), throwsA(isA<TimeoutException>()));
      expect(clock.elapsed, lessThan(const Duration(seconds: 4)));
      expect(session.canSendFrame, isFalse);
    } finally {
      await server.close(force: true);
      await listener.cancel();
      await session.dispose();
    }
  });
  test('camera packets preserve time and enforce receiver credits', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final packets = <Uint8List>[];
    final received = Completer<void>();
    WebSocket? peer;
    final listener = server.listen((request) async {
      peer = await WebSocketTransformer.upgrade(request);
      peer!.listen((event) {
        if (event is String) {
          final message = jsonDecode(event) as Map<String, dynamic>;
          if (message['type'] == 'start') {
            expect(message['protocol'], 2);
            expect(message['rotation_degrees'], 270);
            peer!.add(
              jsonEncode({
                'type': 'ready',
                'protocol': 2,
                'sample_fps': 25,
                'max_inflight_frames': 4,
              }),
            );
          } else if (message['type'] == 'stop') {
            peer!.add(
              jsonEncode({'type': 'session_final', 'transcript': 'xin chào'}),
            );
          }
        } else {
          packets.add(Uint8List.fromList(event as List<int>));
          if (packets.length == 4) received.complete();
        }
      });
    });
    final session = LiveLipSession(
      'http://127.0.0.1:${server.port}',
      rotationDegrees: 270,
    );
    try {
      await session.connect();
      final jpeg = Uint8List.fromList([255, 216, 255, 217]);
      for (var i = 0; i < 4; i++) {
        expect(session.sendFrame(jpeg, capturedAtMs: i * 47.5), isTrue);
      }
      expect(session.sendFrame(jpeg, capturedAtMs: 200), isFalse);
      await received.future.timeout(const Duration(seconds: 3));
      final header = ByteData.sublistView(packets.last);
      expect(packets.last.sublist(0, 4), [76, 73, 80, 50]);
      expect(header.getUint32(4, Endian.big), 3);
      expect(header.getFloat64(8, Endian.big), 142.5);
      expect(packets.last.sublist(16), jpeg);
      expect(await session.stop(), 'xin chào');
      expect(session.canSendFrame, isFalse);
    } finally {
      await session.dispose();
      await peer?.close();
      await listener.cancel();
      await server.close(force: true);
    }
  });
}
