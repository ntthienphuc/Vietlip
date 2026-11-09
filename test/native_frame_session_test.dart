import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/frame_encoder_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'a queued old native JPEG cannot establish the next session clock',
    () async {
      const events = MethodChannel('vn.lipread/native_frames');
      const control = MethodChannel('vn.lipread/native_frames/control');
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      final tokens = <String>[];
      final acknowledged = <int>[];
      messenger.setMockMethodCallHandler(events, (call) async {
        if (call.method == 'listen') {
          tokens.add((call.arguments as Map)['sessionToken'] as String);
        }
        return null;
      });
      messenger.setMockMethodCallHandler(control, (call) async {
        acknowledged.add((call.arguments as Map)['id'] as int);
        return null;
      });
      addTearDown(() {
        messenger.setMockMethodCallHandler(events, null);
        messenger.setMockMethodCallHandler(control, null);
      });
      Future<void> emit(int id, String token, double timestamp) async {
        await messenger.handlePlatformMessage(
          events.name,
          const StandardMethodCodec().encodeSuccessEnvelope({
            'id': id,
            'sessionToken': token,
            'capturedAtMs': timestamp,
            'jpeg': Uint8List.fromList([255, 216, 255, 217]),
            'encodeMicros': 100,
          }),
          (_) {},
        );
        await Future<void>.delayed(Duration.zero);
      }

      final first = <NativeCameraFrame>[];
      final subscription = nativeCameraFrames(25).listen(first.add);
      await Future<void>.delayed(Duration.zero);
      await emit(1, tokens.single, 11000);
      expect(first.single.capturedAtMs, 11000);
      await subscription.cancel();
      final second = <NativeCameraFrame>[];
      final next = nativeCameraFrames(25).listen(second.add);
      await Future<void>.delayed(Duration.zero);
      expect(tokens[0], isNot(tokens[1]));
      await emit(2, tokens[0], 11346.98);
      await emit(3, tokens[1], 0);
      await emit(4, tokens[1], 40);
      expect(second.map((f) => f.capturedAtMs), [0.0, 40.0]);
      expect(acknowledged, contains(2));
      await next.cancel();
    },
  );
}
