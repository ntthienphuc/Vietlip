import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../data/camera_frame_encoder.dart';
import '../../data/frame_encoder_service.dart';
import '../../data/capture_cadence.dart';
import '../../data/capture_storage.dart';
import '../../models/transcription_result.dart';
import '../../models/reading_method.dart';
import '../../data/transcript_review.dart';
import '../../data/live_sentence_recovery.dart';
import '../../data/history_repository.dart';
import '../../data/live_lip_session.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';
import '../../widgets/app_shell.dart';
import '../../widgets/app_brand.dart';
import 'live_caption_panel.dart';
import 'sentence_caption_panel.dart';
import '../settings/reading_method_setting.dart';
import 'camera_viewport.dart';
import 'capture_camera_panel.dart';
import 'live_capture_layout.dart';
import 'capture_ready_layout.dart';
import 'server_connection_banner.dart';
import '../../widgets/status_notice.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({
    required this.settings,
    required this.history,
    super.key,
  });

  final SettingsController settings;
  final HistoryRepository history;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen>
    with WidgetsBindingObserver {
  static const _maxLiveDuration = Duration(minutes: 5);
  static const _maxFullClipDuration = Duration(seconds: 45);

  final _imagePicker = ImagePicker();
  final _scrollController = ScrollController();
  CameraController? _camera;
  List<CameraDescription> _cameras = const [];
  XFile? _video;
  Timer? _timer;
  final _captureClock = Stopwatch();
  final _captureCadence = CaptureCadence();
  Duration _recordedFor = Duration.zero;
  bool _initializing = true;
  bool _initializationInFlight = false;
  bool _suspendingCamera = false;
  bool _submitting = false;
  bool _changingRecording = false;
  double _uploadProgress = 0;
  String _processingStatus = 'Đang chuẩn bị video…';
  String? _error;
  bool _liveWasActive = false;
  bool _encodingLiveFrame = false;
  int _cameraFrames = 0;
  int _encodedFrames = 0;
  int _encodeMicros = 0;
  LiveLipSession? _liveSession;
  StreamSubscription<LiveLipUpdate>? _liveSubscription;
  StreamSubscription<NativeCameraFrame>? _nativeFrames;
  String _liveTranscript = '';
  String _liveStableTranscript = '';
  String _liveStatus = 'Sẵn sàng tạo phụ đề trực tiếp';
  String _liveModelId = 'unknown';
  int _liveReceivedFrames = 0;
  bool _liveIncomplete = false;
  bool _foreground = false;
  String _liveProvisional = '';
  String _liveState = 'waiting_for_face';
  String? _liveWarning;
  double? _liveFps;
  int? _liveElapsedMs;
  Map<String, dynamic> _liveEvidence = const {};
  TranscriptionResult? _lastLiveResult;
  ReadingMethod _sessionMethod = ReadingMethod.visual;
  String _sessionServerAddress = '';
  LiveSentenceRecovery? _sentenceRecovery;

  bool get _isRecording => _camera?.value.isRecordingVideo == true;
  bool get _showLiveSession =>
      (_isRecording ||
      (_changingRecording && _liveWasActive && _liveSession != null));
  Duration get _activeMaxDuration => _maxLiveDuration;
  bool get _canRunFullClip =>
      _recordedFor == Duration.zero || _recordedFor <= _maxFullClipDuration;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.settings.addListener(_settingsChanged);
  }

  void _settingsChanged() {
    if (mounted) setState(() {});
  }

  void _sentenceChanged() {
    if (mounted) setState(() {});
  }

  void _releaseRecovery() {
    final previous = _sentenceRecovery;
    _sentenceRecovery = null;
    if (previous == null) return;
    previous.removeListener(_sentenceChanged);
    unawaited(previous.settled.then((_) => previous.dispose()));
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final active = CaptureVisibility.of(context);
    if (active == _foreground) return;
    _foreground = active;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_foreground && _camera == null && !_suspendingCamera) {
        unawaited(_initializeCamera());
      } else if (!_foreground) {
        unawaited(_suspendCamera());
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.settings.removeListener(_settingsChanged);
    _releaseRecovery();
    _timer?.cancel();
    unawaited(_closeLiveSession());
    _scrollController.dispose();
    _camera?.dispose();
    super.dispose();
  }

  void _revealSelectedVideo() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_foreground || !_scrollController.hasClients) return;
      final target = (_scrollController.position.maxScrollExtent * 0.72).clamp(
        0.0,
        _scrollController.position.maxScrollExtent,
      );
      if (MediaQuery.disableAnimationsOf(context)) {
        _scrollController.jumpTo(target);
        return;
      }
      unawaited(
        _scrollController.animateTo(
          target,
          duration: const Duration(milliseconds: 450),
          curve: Curves.easeOutCubic,
        ),
      );
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      // Android's first permission dialog briefly deactivates the app. Let the
      // pending initialization finish instead of opening a second CameraX use case.
      if (_initializationInFlight && _camera == null) return;
      unawaited(_suspendCamera());
    } else if (state == AppLifecycleState.resumed &&
        _foreground &&
        _camera == null &&
        !_initializationInFlight &&
        !_suspendingCamera) {
      unawaited(_initializeCamera());
    }
  }

  Future<void> _suspendCamera() async {
    if (_suspendingCamera) return;
    _suspendingCamera = true;
    try {
      if (_isRecording) await _stopRecording();
      _timer?.cancel();
      await _closeLiveSession();
      final controller = _camera;
      _camera = null;
      await controller?.dispose();
    } finally {
      _suspendingCamera = false;
      if (mounted &&
          _foreground &&
          WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
        unawaited(_initializeCamera());
      }
    }
  }

  Future<void> _initializeCamera([CameraDescription? requested]) async {
    if (_initializationInFlight || _suspendingCamera || !_foreground) return;
    _initializationInFlight = true;
    if (mounted) {
      setState(() {
        _initializing = true;
        _error = null;
      });
    }
    CameraController? pending;
    try {
      // CameraX unbinds every use case when a controller is disposed. Release
      // the previous lens before binding the replacement preview.
      final previous = _camera;
      _camera = null;
      await previous?.dispose();
      if (!mounted || !_foreground) return;
      _cameras = await availableCameras();
      if (_cameras.isEmpty) throw StateError('Thiết bị không có camera.');
      final selected =
          requested ??
          _cameras.firstWhere(
            (item) => item.lensDirection == CameraLensDirection.front,
            orElse: () => _cameras.first,
          );
      final controller = CameraController(
        selected,
        ResolutionPreset.medium,
        // Audio is saved in the local MP4 for reference transcription only.
        // LiveLipSession sends JPEG frames; microphone samples never enter VSR.
        enableAudio: true,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );
      pending = controller;
      debugPrint('Lip camera: initializing ${selected.name}');
      await controller.initialize().timeout(const Duration(seconds: 20));
      debugPrint('Lip camera: initialized');
      await controller
          .lockCaptureOrientation(DeviceOrientation.portraitUp)
          .timeout(const Duration(seconds: 3));
      debugPrint(
        'Lip camera: locked=${controller.value.lockedCaptureOrientation} '
        'device=${controller.value.deviceOrientation} '
        'sensor=${selected.sensorOrientation}',
      );
      if (!mounted || !_foreground) return;
      _camera = controller;
      pending = null;
    } on CameraException catch (error) {
      _error = switch (error.code) {
        'CameraAccessDenied' || 'CameraAccessDeniedWithoutPrompt' =>
          'Bạn cần cấp quyền camera để quay khuôn mặt.',
        'AudioAccessDenied' || 'AudioAccessDeniedWithoutPrompt' =>
          'Cần quyền microphone để lưu video có tiếng. Bật quyền Microphone trong Cài đặt của điện thoại rồi mở lại màn hình quay.',
        _ => 'Không mở được camera: ${error.description ?? error.code}',
      };
    } catch (error) {
      _error = error.toString();
    } finally {
      try {
        await pending?.dispose();
      } finally {
        _initializationInFlight = false;
        if (mounted) setState(() => _initializing = false);
      }
    }
  }

  Future<void> _flipCamera() async {
    final current = _camera?.description;
    if (current == null || _cameras.length < 2 || _isRecording) return;
    final next = _cameras.firstWhere(
      (item) => item.lensDirection != current.lensDirection,
      orElse: () => _cameras.first,
    );
    await _initializeCamera(next);
  }

  Future<void> _toggleRecording() async {
    final controller = _camera;
    if (controller == null ||
        !controller.value.isInitialized ||
        _submitting ||
        _changingRecording) {
      return;
    }
    if (_isRecording) {
      await _stopRecording();
      return;
    }
    setState(() {
      _changingRecording = true;
      _error = null;
      _liveStatus = 'Đang kết nối máy chủ…';
    });
    try {
      final liveSession = await _openLiveSession(controller);
      if (!mounted || !_foreground) {
        await _closeLiveSession();
        return;
      }
      _cameraFrames = _encodedFrames = _encodeMicros = 0;
      _captureClock
        ..reset()
        ..start();
      if (mounted) setState(() => _liveStatus = 'Đang mở luồng camera…');
      await controller.startVideoRecording(onAvailable: _handleLiveFrame);
      // Subscribe after CameraX has rebound recording use cases. Preview-only
      // frames before that transition would create a false capture gap.
      if (usesNativeFrameEncoder) {
        _nativeFrames = nativeCameraFrames(liveSession.sampleFps).listen(
          _handleNativeFrame,
          onError: (Object error) {
            debugPrint('Lip native frame error: $error');
            if (mounted) {
              setState(() => _liveStatus = 'Bỏ qua một khung hình bị lỗi…');
            }
          },
        );
      }
      debugPrint(
        'Lip camera: recording=${controller.value.recordingOrientation} '
        'locked=${controller.value.lockedCaptureOrientation} '
        'device=${controller.value.deviceOrientation} '
        'preview=${controller.value.previewSize}',
      );
      _timer?.cancel();
      setState(() {
        _video = null;
        _recordedFor = Duration.zero;
        _error = null;
        _liveWasActive = true;
        _liveTranscript = '';
        _liveStableTranscript = '';
        _liveModelId = 'unknown';
        _liveReceivedFrames = 0;
        _liveIncomplete = false;
        _liveProvisional = '';
        _liveWarning = null;
        _liveEvidence = const {};
        _liveFps = null;
        _liveElapsedMs = null;
        _liveState = 'waiting_for_face';
        _liveStatus = _cameraFrames == 0
            ? 'Đang mở luồng camera…'
            : 'Bắt đầu nói · nhìn thẳng vào camera';
      });
      if (mounted) {
        const CaptureSessionNotification(true).dispatch(context);
      }
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!mounted) return;
        final next = Duration(seconds: timer.tick);
        setState(() => _recordedFor = next);
        if (next >= _activeMaxDuration) unawaited(_stopRecording());
      });
    } catch (error) {
      await _closeLiveSession();
      if (mounted) {
        final message = error is StateError
            ? error.message.toString()
            : 'Không thể bắt đầu quay. Hãy thử mở lại camera.';
        setState(() {
          _error = message;
          _liveWarning = message;
          _liveStatus = message;
          _liveState = 'disconnected';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(message),
            duration: const Duration(seconds: 7),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _changingRecording = false);
    }
  }

  Future<LiveLipSession> _openLiveSession(CameraController controller) async {
    if (widget.settings.apiUrl.isEmpty) {
      throw StateError(
        'Vào Cài đặt và nhập IP hiển thị trên VietLip Server. Điện thoại và máy tính cần cùng Wi-Fi.',
      );
    }
    if (!controller.supportsImageStreaming()) {
      throw StateError(
        'Camera này không hỗ trợ live. Hãy thử camera khác hoặc chọn video có sẵn.',
      );
    }
    await _closeLiveSession();
    _sessionMethod = widget.settings.readingMethod;
    _sessionServerAddress = widget.settings.apiUrl;
    final provider = widget.settings.aiProvider;
    final address = _sessionServerAddress;
    final method = _sessionMethod;
    _releaseRecovery();
    _sentenceRecovery = LiveSentenceRecovery(
      sessionId: 'live-${DateTime.now().microsecondsSinceEpoch}',
      method: method,
      provider: provider,
      call: (text, id) => LipReaderApi.atAddress(
        address,
      ).rewrite(text, method, provider: provider, sentenceId: id),
    )..addListener(_sentenceChanged);
    _lastLiveResult = null;
    if (mounted) setState(() => _liveStatus = 'Đang kết nối phụ đề…');
    final connectClock = Stopwatch()..start();
    try {
      final session = LiveLipSession(
        widget.settings.apiUrl,
        onConnectionStage: (message) {
          if (mounted) setState(() => _liveStatus = message);
        },
        rotationDegrees: usesNativeFrameEncoder
            ? controller.description.sensorOrientation
            : 0,
      );
      await session.connect();
      debugPrint(
        'Lip connection: ready_ms=${connectClock.elapsedMilliseconds}',
      );
      if (!session.autoEndpoint) {
        await session.dispose();
        throw StateError(
          'Cần cập nhật server để dùng tự động nhận biết đang nói.',
        );
      }
      _liveSession = session;
      _liveSubscription = session.updates.listen(_handleLiveUpdate);
      if (mounted) {
        setState(() => _liveStatus = 'Đang thu nhận chuyển động môi…');
      }
      return session;
    } catch (error) {
      debugPrint('Live connection failed: $error');
      if (error is StateError) rethrow;
      throw StateError(
        error is TimeoutException
            ? 'Máy chủ chưa phản hồi sau 6 giây. Kiểm tra Wi-Fi và máy chủ rồi bấm thử lại.'
            : 'Chưa kết nối được máy chủ. Kiểm tra Wi-Fi và địa chỉ trong Cài đặt rồi thử lại.',
      );
    }
  }

  void _handleLiveUpdate(LiveLipUpdate update) {
    if (!mounted) return;
    setState(() {
      _liveFps = update.captureFps ?? _liveFps;
      _liveElapsedMs = update.elapsedMs ?? _liveElapsedMs;
      _liveState = update.recognitionState ?? _liveState;
      _liveReceivedFrames = update.receivedFrames ?? _liveReceivedFrames;
      _liveIncomplete = _liveIncomplete || update.incomplete;
      if (update.evidence.isNotEmpty) _liveEvidence = update.evidence;
      if (update.type == 'activity' && _liveState == 'speaking') {
        _liveWarning = null;
      }
      if (update.type == 'partial' ||
          update.type == 'segment_final' ||
          update.type == 'session_final') {
        _liveTranscript = update.transcript;
        _liveStableTranscript = update.stableTranscript;
        _liveProvisional = update.provisionalTranscript;
        _liveWarning = null;
        _liveModelId = update.modelId ?? _liveModelId;
      } else if (update.type == 'notice' ||
          update.type == 'disconnected' ||
          update.type == 'error') {
        _liveWarning = update.message;
        _liveProvisional = '';
        _liveTranscript = _liveStableTranscript;
      }
      _liveStatus = update.type == 'session_final'
          ? 'Đã hoàn tất phiên'
          : _liveWarning ?? liveStatusLabel(_liveState, update.decoderState);
    });
    _sentenceRecovery?.accept(update);
    if (update.captionEventId != null) {
      final session = _liveSession;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        // A later update may replace this one before Flutter draws a frame.
        // Acknowledge only captions present in this session's rendered state.
        if (mounted &&
            _foreground &&
            _showLiveSession &&
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed &&
            ModalRoute.of(context)?.isCurrent != false &&
            identical(session, _liveSession) &&
            _liveTranscript == update.transcript) {
          session?.acknowledgeCaptionFrame(update);
        }
      });
    }
  }

  void _handleLiveFrame(CameraImage image) {
    // The callback enables CameraX ImageAnalysis. On Android its queued Pigeon
    // events can still arrive across stop/start, but only native JPEG events
    // own the capture clock. Mixing these two paths sends time backwards.
    if (usesNativeFrameEncoder) {
      if (_cameraFrames < 3) {
        debugPrint(
          'Lip transport: skipped Dart camera callback; native stream owns timestamps',
        );
      }
      return;
    }
    _showCameraReady();
    _cameraFrames++;
    final session = _liveSession;
    if (session == null || !session.canSendFrame || _encodingLiveFrame) return;
    final captureUs = _captureClock.elapsedMicroseconds;
    if (!_captureCadence.accept(captureUs, session.sampleFps)) return;
    final capturedAtMs = captureUs / 1000.0;
    _encodingLiveFrame = true;
    final encodeClock = Stopwatch()..start();
    final payload = copyCameraFrame(
      image,
      rotationDegrees: _camera?.description.sensorOrientation ?? 0,
    );
    unawaited(
      encodeLiveFrame(payload)
          .then((jpeg) {
            if (jpeg != null) {
              session.sendFrame(jpeg, capturedAtMs: capturedAtMs);
            }
          })
          .catchError((Object _) {
            if (mounted) {
              setState(
                () => _liveStatus =
                    'Không nén được một khung hình; video vẫn tiếp tục được lưu.',
              );
            }
          })
          .whenComplete(() {
            _encodedFrames++;
            _encodeMicros += encodeClock.elapsedMicroseconds;
            _encodingLiveFrame = false;
          }),
    );
  }

  void _handleNativeFrame(NativeCameraFrame frame) {
    try {
      _showCameraReady();
      _cameraFrames++;
      final session = _liveSession;
      if (session == null || !session.canSendFrame) return;
      if (!session.sendFrame(frame.jpeg, capturedAtMs: frame.capturedAtMs)) {
        return;
      }
      if (_encodedFrames < 3) {
        debugPrint(
          'Lip transport: native frame=$_encodedFrames timestamp_ms=${frame.capturedAtMs}',
        );
      }
      _encodedFrames++;
      _encodeMicros += frame.encodeMicros;
    } finally {
      unawaited(frame.acknowledge());
    }
  }

  void _showCameraReady() {
    if (_cameraFrames == 0 && mounted && _liveSession != null) {
      setState(() => _liveStatus = 'Bắt đầu nói · nhìn thẳng vào camera');
    }
  }

  Future<String?> _closeLiveSession() async {
    await _nativeFrames?.cancel();
    _nativeFrames = null;
    final session = _liveSession;
    if (session != null) {
      for (var attempt = 0; attempt < 10 && _encodingLiveFrame; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
    }
    final finalTranscript = session == null ? null : await session.stop();
    if (identical(session, _liveSession)) _liveSession = null;
    if (session != null) {
      debugPrint(
        'Lip transport: rejected_stale_timestamps=${session.rejectedTimestampFrames}',
      );
    }
    await _liveSubscription?.cancel();
    _liveSubscription = null;
    _encodingLiveFrame = false;
    _captureCadence.reset();
    return finalTranscript;
  }

  Future<void> _stopRecording() async {
    final controller = _camera;
    if (controller == null ||
        !controller.value.isRecordingVideo ||
        _changingRecording) {
      return;
    }
    setState(() => _changingRecording = true);
    _timer?.cancel();
    try {
      final temporaryVideo = await controller.stopVideoRecording();
      _captureClock.stop();
      debugPrint(
        'Lip transport: camera=$_cameraFrames encoded=$_encodedFrames '
        'seconds=${_captureClock.elapsedMilliseconds / 1000} '
        'encode_ms=${_encodeMicros / (_encodedFrames == 0 ? 1 : _encodedFrames) / 1000}',
      );
      // Expose the cache immediately, even if durable storage is unavailable.
      if (mounted) setState(() => _video = temporaryVideo);
      XFile video = temporaryVideo;
      try {
        video = XFile(await preserveRecording(temporaryVideo.path));
      } catch (_) {
        if (mounted) {
          setState(
            () => _error =
                'Chưa lưu được bản bền vững; hãy xử lý video trước khi đóng app.',
          );
        }
      }
      if (mounted) {
        setState(() => _liveStatus = 'Đang hoàn tất phần phụ đề cuối…');
      }
      final finalTranscript = await _closeLiveSession();
      if (finalTranscript == null) _liveIncomplete = true;
      final savedTranscript = finalTranscript?.trim().isNotEmpty == true
          ? finalTranscript!.trim()
          : _liveTranscript.trim();
      if (savedTranscript.isNotEmpty) {
        final recovery = _sentenceRecovery;
        recovery?.accept(
          LiveLipUpdate(
            type: 'session_final',
            transcript: savedTranscript,
            stableTranscript: savedTranscript,
          ),
        );
        final saved = TranscriptionResult(
          requestId: 'live-${DateTime.now().microsecondsSinceEpoch}',
          transcript: savedTranscript,
          status: 'review_required',
          modelId: _liveModelId,
          elapsedMs: _captureClock.elapsedMilliseconds,
          numFrames: _liveReceivedFrames,
          createdAt: DateTime.now(),
          alternatives: const [],
          processingMode: 'visual_only',
          riskNotice: _liveIncomplete
              ? 'Một số đoạn chưa nhận dạng được; bản ghi có thể thiếu nội dung.'
              : 'Phụ đề trực tiếp cần được rà soát.',
          diagnostics: {
            'source': 'realtime',
            'incomplete': _liveIncomplete,
            'evidence': _liveEvidence,
            'video_path': video.path,
            'reading_method': _sessionMethod.id,
            'ai_provider': recovery?.provider.id,
          },
          sentences: recovery?.sentences ?? const [],
        );
        await widget.history.add(saved);
        _lastLiveResult = saved;
        if (recovery != null) {
          unawaited(_saveSentenceUpdates(recovery, saved, widget.history));
        }
      }
      if (mounted) {
        setState(() {
          _video = video;
          if (finalTranscript?.trim().isNotEmpty == true) {
            _liveTranscript = finalTranscript!.trim();
          }
          _liveStatus = _liveTranscript.isEmpty
              ? _canRunFullClip
                    ? 'Video đã lưu; có thể xử lý đầy đủ để nhận kết quả.'
                    : 'Video đã lưu nhưng chưa tạo được phụ đề rõ ràng cho phiên này.'
              : _canRunFullClip
              ? 'Phụ đề đã dừng; có thể xử lý video để xác nhận kết quả cuối.'
              : 'Phiên dài đã hoàn tất; phụ đề trực tiếp cần được rà soát.';
        });
        _revealSelectedVideo();
      }
    } catch (error) {
      await _closeLiveSession();
      if (mounted) setState(() => _error = 'Không thể lưu video: $error');
    } finally {
      if (mounted) {
        setState(() => _changingRecording = false);
        CaptureSessionNotification(_isRecording).dispatch(context);
      }
    }
  }

  Future<void> _saveSentenceUpdates(
    LiveSentenceRecovery recovery,
    TranscriptionResult saved,
    HistoryRepository history,
  ) async {
    void persist() {
      unawaited(
        history
            .replaceIfPresent(saved.withSentences(recovery.sentences))
            .catchError((Object _) {}),
      );
    }

    recovery.addListener(persist);
    persist();
    await recovery.settled;
    recovery.removeListener(persist);
    persist();
  }

  Future<void> _pickVideo() async {
    if (_isRecording || _submitting) return;
    final video = await _imagePicker.pickVideo(
      source: ImageSource.gallery,
      maxDuration: _maxFullClipDuration,
    );
    if (video != null && mounted) {
      setState(() {
        _video = video;
        _recordedFor = Duration.zero;
        _liveWasActive = false;
        _error = null;
      });
      _revealSelectedVideo();
    }
  }

  Future<void> _submit() async {
    final video = _video;
    if (video == null || _submitting) return;
    if (!_canRunFullClip) {
      setState(
        () => _error =
            'Phiên trên 45 giây dùng phụ đề trực tiếp; xử lý full-clip chỉ nhận tối đa 45 giây.',
      );
      return;
    }
    setState(() {
      _submitting = true;
      _uploadProgress = 0;
      _processingStatus = 'Đang chuẩn bị video…';
      _error = null;
    });
    try {
      final method = widget.settings.readingMethod;
      final provider = widget.settings.aiProvider;
      final address = widget.settings.apiUrl;
      final result = await LipReaderApi.atAddress(address).transcribe(
        videoPath: video.path,
        onProgress: (progress) {
          if (mounted) setState(() => _uploadProgress = progress);
        },
        onStatus: (status) {
          if (mounted) setState(() => _processingStatus = status);
        },
      );
      final saved = await saveWithReview(
        result: result,
        settings: widget.settings,
        history: widget.history,
        method: method,
        serverAddress: address,
        aiProvider: provider,
      );
      if (!mounted) return;
      await context.push('/result', extra: saved);
    } catch (error) {
      if (mounted) {
        setState(() => _error = LipReaderApi.readableError(error));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String get _timerLabel {
    String label(Duration value) {
      final minutes = value.inMinutes.toString().padLeft(2, '0');
      final seconds = (value.inSeconds % 60).toString().padLeft(2, '0');
      return '$minutes:$seconds';
    }

    return '${label(_recordedFor)} / ${label(_activeMaxDuration)}';
  }

  @override
  Widget build(BuildContext context) {
    if (_showLiveSession) {
      return LiveCaptureLayout(
        recovery: _sessionMethod.usesAi,
        header: Row(
          children: [
            const BrandMark(size: 32),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _isRecording ? 'Đang đọc môi' : 'Đang hoàn tất phiên…',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        preview: _buildCameraCard(),
        captions: _buildLiveDraft(),
        controls: _buildCaptureControls(),
      );
    }
    if (_video == null && !_liveWasActive) {
      return CaptureReadyLayout(
        recovery: widget.settings.readingMethod.usesAi,
        header: Row(
          children: [
            const Expanded(child: CaptureBrandHeader()),
            IconButton(
              tooltip: 'Chế độ đọc môi: ${widget.settings.readingMethod.label}',
              onPressed: _changingRecording
                  ? null
                  : () => ReadingMethodSetting.showPicker(
                      context,
                      widget.settings,
                    ),
              icon: Icon(
                widget.settings.readingMethod.usesAi
                    ? Icons.auto_awesome_rounded
                    : Icons.closed_caption_outlined,
                size: 20,
              ),
            ),
            IconButton(
              tooltip: 'Hướng dẫn đọc môi',
              onPressed: _changingRecording ? null : _showCaptureOptions,
              icon: const Icon(Icons.help_outline_rounded),
            ),
          ],
        ),
        connection: ServerConnectionBanner(
          settings: widget.settings,
          active: _foreground,
          onConfigure: () => context.go('/settings'),
        ),
        preview: _buildCameraCard(),
        captions: _buildLiveDraft(idle: true),
        notice: _error == null
            ? null
            : StatusNotice(
                title: 'Chưa thể bắt đầu',
                detail: _error,
                error: true,
                action: _liveState == 'disconnected'
                    ? 'Kiểm tra kết nối'
                    : null,
                onAction: _liveState == 'disconnected'
                    ? () => context.go('/settings')
                    : null,
              ),
        controls: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_changingRecording) ...[
              Semantics(
                liveRegion: true,
                child: Text(
                  _liveStatus,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.primary,
                  ),
                ),
              ),
              const SizedBox(height: 8),
            ],
            _buildCaptureControls(),
            const SizedBox(height: 10),
            const Text(
              'Đọc môi bằng hình ảnh · tự chốt khi ngừng nói',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                height: 1.5,
                color: AppColors.muted,
              ),
            ),
          ],
        ),
      );
    }
    return SafeArea(
      child: Column(
        children: [
          Expanded(
            child: CustomScrollView(
              controller: _scrollController,
              slivers: [
                SliverAppBar(
                  floating: true,
                  toolbarHeight: 60,
                  title: const CaptureBrandHeader(),
                  actions: [
                    IconButton(
                      tooltip: 'Hướng dẫn đọc môi',
                      onPressed: _changingRecording
                          ? null
                          : _showCaptureOptions,
                      icon: const Icon(Icons.help_outline_rounded),
                    ),
                  ],
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                  sliver: SliverList.list(
                    children: [
                      ServerConnectionBanner(
                        settings: widget.settings,
                        active: _foreground,
                        onConfigure: () => context.go('/settings'),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        height: (MediaQuery.sizeOf(context).height * .30).clamp(
                          260.0,
                          380.0,
                        ),
                        child: _buildCameraCard(),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        StatusNotice(
                          title: 'Chưa thể hoàn tất',
                          detail: _error,
                          error: true,
                          action: _liveState == 'disconnected'
                              ? 'Kiểm tra kết nối'
                              : null,
                          onAction: _liveState == 'disconnected'
                              ? () => context.go('/settings')
                              : null,
                        ),
                      ],
                      const SizedBox(height: 12),
                      _buildLiveDraft(idle: !_liveWasActive),
                      if (_video != null) ...[
                        const SizedBox(height: 20),
                        if (_lastLiveResult != null) ...[
                          OutlinedButton.icon(
                            onPressed: () =>
                                context.push('/result', extra: _lastLiveResult),
                            icon: const Icon(Icons.article_outlined),
                            label: const Text('Xem bản đã lưu'),
                          ),
                          const SizedBox(height: 12),
                        ],
                        _buildSelectedVideo(),
                        const SizedBox(height: 12),
                        if (_canRunFullClip)
                          _buildFullClipControls()
                        else
                          _buildContinuousOnlyNote(),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            decoration: const BoxDecoration(
              color: AppColors.canvas,
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_changingRecording) ...[
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      _liveStatus,
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 13,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                _buildCaptureControls(),
                const SizedBox(height: 10),
                const Text(
                  'Đọc môi bằng hình ảnh · tự chốt khi ngừng nói',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    height: 1.5,
                    color: AppColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFullClipControls() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      FilledButton.icon(
        onPressed: _submitting ? null : _submit,
        icon: _submitting
            ? const SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.closed_caption_outlined),
        label: Text(
          _submitting
              ? _uploadProgress < 1
                    ? 'Đang gửi video ${(_uploadProgress * 100).round()}%'
                    : 'Đang đọc video…'
              : 'Đọc môi từ video này',
        ),
      ),
      if (_submitting) ...[
        const SizedBox(height: 12),
        LinearProgressIndicator(
          value: _uploadProgress < 1 ? _uploadProgress : null,
        ),
        const SizedBox(height: 8),
        Semantics(
          liveRegion: true,
          child: Text(
            '$_processingStatus\nGiữ ứng dụng mở để nhận kết quả.',
            style: const TextStyle(color: AppColors.muted, height: 1.5),
          ),
        ),
      ],
    ],
  );

  Widget _buildContinuousOnlyNote() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.warningSoft,
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.closed_caption_outlined, color: AppColors.warning),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Phiên dài hơn 45 giây dùng phụ đề trực tiếp tích lũy. Video vẫn '
              'được lưu trên điện thoại, nhưng không gửi nguyên clip lên server.',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }

  void _showCaptureOptions() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Đọc môi trực tiếp',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              const Text(
                'Nhìn thẳng vào camera, nói từng câu và nghỉ tự nhiên. Ứng dụng tự chốt câu khi bạn ngừng nói.',
                style: TextStyle(height: 1.6),
              ),
              const SizedBox(height: 20),
              _buildTips(),
              const SizedBox(height: 16),
              const Text(
                'Mỗi phiên tối đa 5 phút. Khi bật Kèm gợi ý câu, máy tính gửi phần chữ đã chốt đến Google Gemini. Mô hình ngôn ngữ lớn (LLM) đề xuất cách diễn đạt. Bạn có thể so với phụ đề gốc ngay phía trên.',
                style: TextStyle(color: AppColors.muted, height: 1.5),
              ),
              const SizedBox(height: 10),
              const Text(
                'Preview có thể cắt bớt mép ảnh để vừa khung, luôn giữ đúng tỷ lệ. Nhận dạng dùng khung hình gốc. Video lưu có âm thanh để xem lại; đọc môi chỉ dùng hình ảnh.',
                style: TextStyle(color: AppColors.muted, height: 1.5),
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Đã hiểu'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCameraCard() {
    final controller = _camera;
    final Widget preview;
    if (_initializing) {
      preview = const Center(
        child: CircularProgressIndicator(color: Colors.white),
      );
    } else if (controller?.value.isInitialized == true) {
      const guide = CustomPaint(painter: FaceGuidePainter());
      preview = usesNativeFrameEncoder
          ? NativeCameraPreview(textureId: controller!.cameraId, overlay: guide)
          : CameraViewport(
              sourceSize: Size(
                controller!.value.previewSize!.height,
                controller.value.previewSize!.width,
              ),
              fit: BoxFit.cover,
              overlay: guide,
              child: CameraPreview(controller),
            );
    } else {
      preview = Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.videocam_off_outlined,
                color: Colors.white70,
                size: 34,
              ),
              const SizedBox(height: 12),
              const Text(
                'Camera chưa sẵn sàng',
                style: TextStyle(color: Colors.white),
              ),
              TextButton(
                onPressed: _initializeCamera,
                child: const Text('Mở lại camera'),
              ),
            ],
          ),
        ),
      );
    }
    return CaptureCameraPanel(
      preview: preview,
      recording: _isRecording,
      timerLabel: _timerLabel,
      onFlip: _changingRecording || _submitting ? null : _flipCamera,
    );
  }

  Widget _buildCaptureControls() {
    final busy = _submitting || _changingRecording;
    final initialized = _camera?.value.isInitialized == true;
    final configured = widget.settings.apiUrl.isNotEmpty;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (!_isRecording && !_changingRecording) ...[
          IconButton.outlined(
            tooltip: 'Chọn video có sẵn',
            onPressed: busy ? null : _pickVideo,
            style: IconButton.styleFrom(
              minimumSize: const Size(56, 56),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              side: const BorderSide(color: AppColors.border),
            ),
            icon: const Icon(Icons.video_library_outlined),
          ),
          const SizedBox(width: 12),
        ],
        Expanded(
          child: FilledButton.icon(
            style: _isRecording
                ? FilledButton.styleFrom(backgroundColor: AppColors.error)
                : null,
            onPressed: busy || !initialized
                ? null
                : !configured && !_isRecording
                ? () => context.go('/settings')
                : _toggleRecording,
            icon: _changingRecording
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(
                    _isRecording
                        ? Icons.stop_rounded
                        : configured
                        ? Icons.play_arrow_rounded
                        : Icons.wifi_rounded,
                  ),
            label: Text(
              _changingRecording
                  ? _isRecording
                        ? 'Đang kết thúc…'
                        : 'Đang chuẩn bị…'
                  : _isRecording
                  ? 'Kết thúc phiên'
                  : configured
                  ? 'Bắt đầu đọc môi'
                  : 'Kết nối máy tính',
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildLiveDraft({bool idle = false}) {
    final recovery = _sentenceRecovery;
    final usesAi = idle
        ? widget.settings.readingMethod.usesAi
        : _sessionMethod.usesAi;
    if (usesAi) {
      return SizedBox(
        height:
            320 +
            (MediaQuery.textScalerOf(context).scale(1) - 1).clamp(0, 3) * 210,
        child: SentenceCaptionPanel(
          controller: recovery,
          sentences: idle ? const [] : recovery?.sentences ?? const [],
          draft: idle ? '' : recovery?.draft ?? '',
          provider: idle
              ? widget.settings.aiProvider
              : recovery?.provider ?? widget.settings.aiProvider,
          status: _liveStatus,
          idle: idle,
        ),
      );
    }
    return SizedBox(
      height:
          (idle ? 220 : 270) +
          (MediaQuery.textScalerOf(context).scale(1) - 1).clamp(0, 3) * 210,
      child: LiveCaptionPanel(
        transcript: _liveTranscript,
        committed: _liveStableTranscript,
        provisional: _liveProvisional,
        status: idle ? 'Chưa bắt đầu' : _liveStatus,
        idle: idle,
        unavailable:
            !idle &&
            (_liveWarning != null ||
                const {
                  'waiting_for_face',
                  'multiple_faces',
                  'face_too_small',
                  'poor_light',
                  'look_straight',
                  'head_motion',
                  'camera_stalled',
                  'activity_unavailable',
                  'disconnected',
                  'network_stalled',
                }.contains(_liveState)),
        captureFps: _liveFps,
        elapsedMs: _liveElapsedMs,
        waitingForCaption: {'speaking', 'pausing'}.contains(_liveState),
        unavailableWindows:
            (_liveEvidence['unavailable_windows'] as num?)?.toInt() ?? 0,
      ),
    );
  }

  Widget _buildSelectedVideo() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: AppColors.primarySoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.check_rounded,
                color: AppColors.primary,
                size: 30,
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _canRunFullClip
                        ? 'Video sẵn sàng'
                        : _liveTranscript.isEmpty
                        ? 'Video của phiên đã lưu'
                        : 'Phiên phụ đề đã sẵn sàng',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Bỏ video',
              onPressed: _submitting
                  ? null
                  : () => setState(() {
                      _video = null;
                      if (_liveTranscript.isEmpty) {
                        _liveWasActive = false;
                        _liveWarning = null;
                      }
                    }),
              icon: const Icon(Icons.close_rounded),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTips() {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Để nhận dạng tự nhiên hơn',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
            ),
            SizedBox(height: 12),
            _Tip(
              icon: Icons.wb_sunny_outlined,
              text: 'Nguồn sáng ở phía trước mặt.',
            ),
            _Tip(
              icon: Icons.face_outlined,
              text: 'Không che miệng, hạn chế quay nghiêng.',
            ),
            _Tip(
              icon: Icons.speed_outlined,
              text: 'Nói tốc độ bình thường, không cường điệu khẩu hình.',
            ),
            _Tip(
              icon: Icons.short_text_rounded,
              text: 'Mỗi lần một câu ngắn, ngắt rõ đầu và cuối.',
            ),
          ],
        ),
      ),
    );
  }
}

class _Tip extends StatelessWidget {
  const _Tip({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          Icon(icon, size: 21, color: AppColors.primary),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
