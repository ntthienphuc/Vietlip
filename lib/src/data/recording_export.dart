import 'package:flutter/services.dart';

/// The Android document picker owns the destination and overwrite prompt.
class RecordingExport {
  static const _channel = MethodChannel('vn.lipread/recordings');

  static Future<bool> save(String path) async {
    if (path.trim().isEmpty) {
      throw ArgumentError.value(path, 'path', 'Missing recording');
    }
    return await _channel.invokeMethod<bool>('exportRecording', {
          'path': path,
        }) ??
        false;
  }
}
