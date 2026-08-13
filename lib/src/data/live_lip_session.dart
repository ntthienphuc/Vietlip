import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:web_socket_channel/web_socket_channel.dart';

class LiveLipUpdate {
  const LiveLipUpdate({
    required this.type,
    this.transcript = '',
    this.stableTranscript = '',
    this.message,
    this.device,
  });

  final String type;
  final String transcript;
  final String stableTranscript;
  final String? message;
  final String? device;

  factory LiveLipUpdate.fromJson(Map<String, dynamic> json) => LiveLipUpdate(
    type: json['type']?.toString() ?? 'unknown',
    transcript: json['transcript']?.toString() ?? '',
    stableTranscript: json['stable_transcript']?.toString() ?? '',
    message: json['message']?.toString(),
    device: json['device']?.toString(),
  );
}

class LiveLipSession {
  LiveLipSession(String apiUrl)
    : endpoint = realtimeEndpoint(apiUrl),
      _updates = StreamController<LiveLipUpdate>.broadcast();

  final Uri endpoint;
  final StreamController<LiveLipUpdate> _updates;
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  bool _stopped = false;
  final Completer<String?> _finalTranscript = Completer<String?>();

  Stream<LiveLipUpdate> get updates => _updates.stream;
  bool get isConnected => _channel != null && !_stopped;

  static Uri realtimeEndpoint(String apiUrl) {
    final source = Uri.parse(apiUrl);
    final scheme = switch (source.scheme.toLowerCase()) {
      'https' => 'wss',
      'http' => 'ws',
      _ => throw const FormatException(
        'Địa chỉ server phải bắt đầu bằng http:// hoặc https://',
      ),
    };
    return source.replace(scheme: scheme, path: '/v1/realtime', query: null);
  }

  Future<void> connect() async {
    final channel = WebSocketChannel.connect(endpoint);
    await channel.ready.timeout(const Duration(seconds: 8));
    _channel = channel;
    _subscription = channel.stream.listen(
      (dynamic event) {
        if (event is! String) return;
        try {
          final decoded = jsonDecode(event);
          if (decoded is Map) {
            final update = LiveLipUpdate.fromJson(
              Map<String, dynamic>.from(decoded),
            );
            _updates.add(update);
            if (update.type == 'session_final' &&
                !_finalTranscript.isCompleted) {
              _finalTranscript.complete(update.transcript);
            }
          }
        } on FormatException {
          // Ignore an invalid server event and keep the recording alive.
        }
      },
      onError: (Object error, StackTrace stackTrace) {
        if (!_finalTranscript.isCompleted) _finalTranscript.complete(null);
        if (!_updates.isClosed) {
          _updates.add(
            const LiveLipUpdate(
              type: 'notice',
              message:
                  'Mất kết nối phụ đề; video vẫn tiếp tục được lưu trên máy.',
            ),
          );
        }
      },
      onDone: () {
        if (!_finalTranscript.isCompleted) _finalTranscript.complete(null);
      },
    );
    channel.sink.add(jsonEncode(const {'type': 'start'}));
  }

  void sendFrame(Uint8List jpeg) {
    if (!isConnected || jpeg.isEmpty) return;
    _channel!.sink.add(jpeg);
  }

  Future<String?> stop() async {
    if (_stopped) {
      return _finalTranscript.isCompleted ? _finalTranscript.future : null;
    }
    _stopped = true;
    final channel = _channel;
    String? transcript;
    if (channel != null) {
      channel.sink.add(jsonEncode(const {'type': 'stop'}));
      try {
        transcript = await _finalTranscript.future.timeout(
          const Duration(seconds: 60),
        );
      } on TimeoutException {
        transcript = null;
      }
      try {
        await channel.sink.close();
      } on Object {
        // The server may close immediately after session_final.
      }
    }
    await _subscription?.cancel();
    if (!_updates.isClosed) await _updates.close();
    _channel = null;
    return transcript;
  }
}
