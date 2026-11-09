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
    this.elapsedMs,
    this.behindLiveMs,
    this.incomplete = false,
    this.modelId,
    this.receivedFrames,
    this.provisionalTranscript = '',
    this.recognitionState,
    this.decoderState,
    this.captureFps,
    this.code,
    this.evidence = const {},
    this.captionEventId,
    this.receiptClock,
  });
  final String type;
  final String transcript;
  final String stableTranscript;
  final String? message;
  final String? device;
  final int? elapsedMs;
  final int? behindLiveMs;
  final bool incomplete;
  final String? modelId;
  final int? receivedFrames;
  final String provisionalTranscript;
  final String? recognitionState;
  final String? decoderState;
  final double? captureFps;
  final String? code;
  final Map<String, dynamic> evidence;
  final int? captionEventId;
  final Stopwatch? receiptClock;
  factory LiveLipUpdate.fromJson(Map<String, dynamic> json) => LiveLipUpdate(
    type: json['type']?.toString() ?? 'unknown',
    transcript: json['transcript']?.toString() ?? '',
    stableTranscript: json['stable_transcript']?.toString() ?? '',
    message: json['message']?.toString(),
    device: json['device']?.toString(),
    elapsedMs: (json['elapsed_ms'] as num?)?.round(),
    behindLiveMs: (json['behind_live_ms'] as num?)?.round(),
    incomplete: json['incomplete'] == true,
    modelId: json['model_id']?.toString(),
    receivedFrames: (json['received_frames'] as num?)?.toInt(),
    provisionalTranscript: json['provisional_transcript']?.toString() ?? '',
    recognitionState: json['recognition_state']?.toString(),
    decoderState: json['decoder_state']?.toString(),
    captureFps: (json['capture_fps'] as num?)?.toDouble(),
    code: json['code']?.toString(),
    evidence: json['evidence'] is Map
        ? Map<String, dynamic>.from(json['evidence'] as Map)
        : const {},
    captionEventId: (json['caption_event_id'] as num?)?.toInt(),
    receiptClock: json['caption_event_id'] == null
        ? null
        : (Stopwatch()..start()),
  );
}

class LiveLipSession {
  LiveLipSession(
    String apiUrl, {
    this.rotationDegrees = 0,
    this.connectTimeout = const Duration(seconds: 6),
    this.onConnectionStage,
  }) : endpoint = realtimeEndpoint(apiUrl);
  final int rotationDegrees;
  final Duration connectTimeout;
  final void Function(String message)? onConnectionStage;
  final Uri endpoint;
  final _updates = StreamController<LiveLipUpdate>.broadcast();
  final _ready = Completer<void>();
  final _finalTranscript = Completer<String?>();
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  bool _stopped = false;
  bool _closed = false;
  bool _readyConfirmed = false;
  double _lastCaptureMs = -1;
  int rejectedTimestampFrames = 0;
  int _sequence = 0;
  int _lastAck = -1;
  int _maxInflight = 4;
  double sampleFps = 25;
  bool supportsFlush = false;
  bool autoEndpoint = false;
  Timer? _watchdog;
  DateTime _lastMessage = DateTime.now();
  bool _networkStalled = false;
  bool _flushPending = false;
  bool get canFlush => isConnected && supportsFlush && !_flushPending;
  Stream<LiveLipUpdate> get updates => _updates.stream;
  bool get isConnected =>
      _channel != null && !_stopped && !_closed && _readyConfirmed;
  bool get canSendFrame =>
      isConnected && _sequence - _lastAck - 1 < _maxInflight;

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
    final clock = Stopwatch()..start();
    onConnectionStage?.call('Đang kết nối máy chủ…');
    final channel = WebSocketChannel.connect(endpoint);
    _channel = channel;
    try {
      await channel.ready.timeout(connectTimeout);
      onConnectionStage?.call('Đã nối máy chủ · đang mở phiên live…');
      _subscription = channel.stream.listen(
        (event) {
          if (event is! String || _closed) return;
          _lastMessage = DateTime.now();
          if (_networkStalled) {
            _networkStalled = false;
            _updates.add(
              const LiveLipUpdate(
                type: 'telemetry',
                recognitionState: 'collecting',
                message: 'Đã kết nối lại luồng hình.',
              ),
            );
          }
          try {
            final json = jsonDecode(event) as Map<String, dynamic>;
            final type = json['type'];
            if (type == 'ack') {
              final ack = (json['sequence'] as num).toInt();
              if (ack > _lastAck && ack < _sequence) _lastAck = ack;
              return;
            }
            if (type == 'ready') {
              if (json['protocol'] != 2) {
                if (!_ready.isCompleted) {
                  _ready.completeError(
                    StateError(
                      'Cần cập nhật Lip Reader Server lên giao thức 2.',
                    ),
                  );
                }
                return;
              }
              sampleFps = ((json['sample_fps'] as num?)?.toDouble() ?? 25)
                  .clamp(1, 30);
              _maxInflight =
                  ((json['max_inflight_frames'] as num?)?.toInt() ?? 4).clamp(
                    1,
                    8,
                  );
              supportsFlush = json['supports_flush'] == true;
              autoEndpoint = json['auto_endpoint'] == true;
              _readyConfirmed = true;
              if (!_ready.isCompleted) _ready.complete();
            }
            if (type == 'error') {
              final message = json['code'] == 'invalid_frame'
                  ? 'Luồng hình bị lỗi. Kết thúc phiên rồi thử lại.'
                  : json['message']?.toString() ??
                        'Máy chủ chưa mở được phiên live.';
              if (!_ready.isCompleted) {
                _ready.completeError(StateError(message));
              }
              if (!_updates.isClosed) {
                _updates.add(
                  LiveLipUpdate(
                    type: 'error',
                    code: json['code']?.toString(),
                    message: message,
                    recognitionState: 'disconnected',
                    incomplete: true,
                  ),
                );
              }
              _closed = true;
              _watchdog?.cancel();
              if (!_finalTranscript.isCompleted) {
                _finalTranscript.complete(null);
              }
              return;
            }
            final update = LiveLipUpdate.fromJson(json);
            if (type == 'segment_final') _flushPending = false;
            if (!_updates.isClosed) _updates.add(update);
            if (type == 'session_final' && !_finalTranscript.isCompleted) {
              _stopped = true;
              _watchdog?.cancel();
              _finalTranscript.complete(update.transcript);
            }
          } on FormatException {
            _notice('Server gửi dữ liệu phụ đề không hợp lệ.');
          } on TypeError {
            _notice('Server gửi dữ liệu phụ đề không hợp lệ.');
          }
        },
        onError: (Object error) => _disconnected(),
        onDone: _disconnected,
      );
      channel.sink.add(
        jsonEncode({
          'type': 'start',
          'protocol': 2,
          'input_kind': 'raw_face',
          'auto_endpoint': true,
          'rotation_degrees': rotationDegrees,
        }),
      );
      final remaining = connectTimeout - clock.elapsed;
      await _ready.future.timeout(
        remaining > Duration.zero ? remaining : Duration.zero,
      );
      _watchdog = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!_stopped &&
            !_closed &&
            !_networkStalled &&
            DateTime.now().difference(_lastMessage).inSeconds >= 5) {
          _networkStalled = true;
          _updates.add(
            const LiveLipUpdate(
              type: 'notice',
              recognitionState: 'network_stalled',
              message:
                  'Mạng đang gián đoạn. Phụ đề có thể thiếu đoạn; video vẫn được lưu.',
            ),
          );
        }
      });
    } catch (_) {
      await dispose();
      rethrow;
    }
  }

  void _notice(String text) {
    if (!_updates.isClosed) {
      _updates.add(LiveLipUpdate(type: 'notice', message: text));
    }
  }

  void _disconnected() {
    if (_closed) return;
    _closed = true;
    if (!_ready.isCompleted) {
      _ready.completeError(StateError('Server đã ngắt kết nối.'));
    }
    if (!_finalTranscript.isCompleted) _finalTranscript.complete(null);
    _watchdog?.cancel();
    if (!_stopped && !_updates.isClosed) {
      _updates.add(
        const LiveLipUpdate(
          type: 'disconnected',
          recognitionState: 'disconnected',
          incomplete: true,
          message:
              'Mất kết nối. Dừng và bắt đầu lại để nối phụ đề; video vẫn được lưu.',
        ),
      );
    }
  }

  bool finishUtterance() {
    if (!canFlush) return false;
    _flushPending = true;
    _channel!.sink.add(jsonEncode(const {'type': 'flush'}));
    return true;
  }

  /// Called after Flutter finishes the frame containing this exact caption.
  /// No wall-clock synchronization or extra camera timestamps are required.
  void acknowledgeCaptionFrame(LiveLipUpdate update) {
    if (!isConnected ||
        update.captionEventId == null ||
        update.receiptClock == null) {
      return;
    }
    _channel!.sink.add(
      jsonEncode({
        'type': 'caption_rendered',
        'caption_event_id': update.captionEventId,
        'receive_to_frame_ms':
            update.receiptClock!.elapsedMicroseconds / 1000.0,
      }),
    );
  }

  bool sendFrame(Uint8List jpeg, {required double capturedAtMs}) {
    if (!canSendFrame || jpeg.isEmpty || !capturedAtMs.isFinite) return false;
    // Never mix epochs or fabricate timestamps to disguise a stale frame.
    if (capturedAtMs < 0 || capturedAtMs <= _lastCaptureMs) {
      rejectedTimestampFrames++;
      return false;
    }
    _lastCaptureMs = capturedAtMs;
    final packet = Uint8List(16 + jpeg.length);
    packet.setAll(0, const [76, 73, 80, 50]);
    final header = ByteData.sublistView(packet);
    header.setUint32(4, _sequence++, Endian.big);
    header.setFloat64(8, capturedAtMs, Endian.big);
    packet.setAll(16, jpeg);
    _channel!.sink.add(packet);
    return true;
  }

  Future<String?> stop() async {
    if (_stopped || _closed) {
      await dispose();
      return _finalTranscript.isCompleted ? _finalTranscript.future : null;
    }
    _stopped = true;
    try {
      _channel?.sink.add(jsonEncode(const {'type': 'stop'}));
      return await _finalTranscript.future.timeout(const Duration(seconds: 30));
    } on TimeoutException {
      return null;
    } finally {
      await dispose();
    }
  }

  Future<void> dispose() async {
    _watchdog?.cancel();
    _closed = true;
    _stopped = true;
    try {
      await _subscription?.cancel().timeout(const Duration(milliseconds: 500));
    } on TimeoutException {
      // A peer that never completes its handshake cannot hold the UI open.
    }
    _subscription = null;
    final channel = _channel;
    _channel = null;
    try {
      await channel?.sink.close().timeout(const Duration(milliseconds: 500));
    } catch (_) {
      /* Already closed. */
    }
    if (!_updates.isClosed) await _updates.close();
  }
}
