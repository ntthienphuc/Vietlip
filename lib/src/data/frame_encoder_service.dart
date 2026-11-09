import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'camera_frame_encoder.dart';

bool get usesNativeFrameEncoder =>
    !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

class NativeCameraFrame {
  NativeCameraFrame(Map<dynamic, dynamic> value)
    : id = value['id'] as int,
      jpeg = value['jpeg'] as Uint8List,
      capturedAtMs = (value['capturedAtMs'] as num).toDouble(),
      encodeMicros = value['encodeMicros'] as int;

  final int id;
  final Uint8List jpeg;
  final double capturedAtMs;
  final int encodeMicros;

  Future<void> acknowledge() => const MethodChannel(
    'vn.lipread/native_frames/control',
  ).invokeMethod<void>('ack', {'id': id});
}

int _nativeSubscriptionId = 0;

Stream<NativeCameraFrame> nativeCameraFrames(double fps) {
  final token =
      '${DateTime.now().microsecondsSinceEpoch}-${++_nativeSubscriptionId}';
  return const EventChannel('vn.lipread/native_frames')
      .receiveBroadcastStream({'fps': fps, 'sessionToken': token})
      .where((value) {
        final data = value as Map<dynamic, dynamic>;
        if (data['sessionToken'] == token) return true;
        // An event already queued in the platform channel can outlive cancel.
        // Reject by session identity before it establishes the new time origin.
        unawaited(
          NativeCameraFrame(data).acknowledge().catchError((Object _) {}),
        );
        return false;
      })
      .map((value) => NativeCameraFrame(value as Map<dynamic, dynamic>));
}

/// Camera callbacks admit only one encode at a time; Android uses its worker
/// thread and JPEG codec, while other platforms retain the Dart isolate path.
Future<Uint8List?> encodeLiveFrame(Map<String, Object> frame) async {
  if (usesNativeFrameEncoder) {
    return const MethodChannel(
      'vn.lipread/frame_encoder',
    ).invokeMethod<Uint8List>('encode', frame);
  }
  return compute(encodeCameraFrame, frame);
}
