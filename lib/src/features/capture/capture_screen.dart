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
import '../../data/history_repository.dart';
import '../../data/live_lip_session.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';
import '../../widgets/app_shell.dart';
import 'live_caption_panel.dart';
import 'camera_viewport.dart';
import 'capture_camera_panel.dart';
import 'live_capture_layout.dart';

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
  final _contextController = TextEditingController();
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
  String _mode = 'visual_only';
  bool _acceptLlmRisk = false;
  bool _livePreviewEnabled = true;
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

  bool get _isRecording => _camera?.value.isRecordingVideo == true;
  Duration get _activeMaxDuration =>
      _livePreviewEnabled ? _maxLiveDuration : _maxFullClipDuration;
  bool get _canRunFullClip =>
      _recordedFor == Duration.zero || _recordedFor <= _maxFullClipDuration;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    _timer?.cancel();
    unawaited(_closeLiveSession());
    _contextController.dispose();
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
    if (_initializationInFlight || !_foreground) return;
    _initializationInFlight = true;
    if (mounted) {
      setState(() {
        _initializing = true;
        _error = null;
      });
    }
    try {
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
      if (!mounted || !_foreground) {
        await controller.dispose();
        return;
      }
      await _camera?.dispose();
      _camera = controller;
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
      _initializationInFlight = false;
      if (mounted) setState(() => _initializing = false);
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
      _liveStatus = _livePreviewEnabled
          ? 'Đang kết nối máy chủ…'
          : 'Đang mở camera…';
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
      await controller.startVideoRecording(
        onAvailable: liveSession == null ? null : _handleLiveFrame,
      );
      // Subscribe after CameraX has rebound recording use cases. Preview-only
      // frames before that transition would create a false capture gap.
      if (liveSession != null && usesNativeFrameEncoder) {
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
        _liveWasActive = _livePreviewEnabled;
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
        CaptureSessionNotification(_livePreviewEnabled).dispatch(context);
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

  Future<LiveLipSession?> _openLiveSession(CameraController controller) async {
    if (!_livePreviewEnabled) return null;
    if (!controller.supportsImageStreaming()) {
      throw StateError(
        'Camera này không hỗ trợ live. Bạn có thể tắt phụ đề trực tiếp để quay video.',
      );
    }
    await _closeLiveSession();
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
    if (update.captionEventId != null) {
      final session = _liveSession;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        // A later update may replace this one before Flutter draws a frame.
        // Acknowledge only captions present in this session's rendered state.
        if (mounted &&
            _foreground &&
            _isRecording &&
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
    _liveSession = null;
    if (session != null) {
      for (var attempt = 0; attempt < 10 && _encodingLiveFrame; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
    }
    final finalTranscript = session == null ? null : await session.stop();
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
    _changingRecording = true;
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
      if (mounted && _livePreviewEnabled) {
        setState(() => _liveStatus = 'Đang hoàn tất phần phụ đề cuối…');
      }
      final finalTranscript = await _closeLiveSession();
      if (finalTranscript == null) _liveIncomplete = true;
      final savedTranscript = finalTranscript?.trim().isNotEmpty == true
          ? finalTranscript!.trim()
          : _liveTranscript.trim();
      if (savedTranscript.isNotEmpty) {
        await widget.history.add(
          TranscriptionResult(
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
                ? 'Phiên bị gián đoạn; bản ghi có thể thiếu nội dung.'
                : 'Phụ đề trực tiếp cần được rà soát.',
            diagnostics: {
              'source': 'realtime',
              'incomplete': _liveIncomplete,
              'evidence': _liveEvidence,
              'video_path': video.path,
            },
          ),
        );
      }
      if (mounted) {
        setState(() {
          _video = video;
          if (finalTranscript?.trim().isNotEmpty == true) {
            _liveTranscript = finalTranscript!.trim();
          }
          if (_livePreviewEnabled) {
            _liveStatus = _liveTranscript.isEmpty
                ? _canRunFullClip
                      ? 'Video đã lưu; có thể xử lý đầy đủ để nhận kết quả.'
                      : 'Video đã lưu nhưng chưa tạo được phụ đề rõ ràng cho phiên này.'
                : _canRunFullClip
                ? 'Phụ đề đã dừng; có thể xử lý video để xác nhận kết quả cuối.'
                : 'Phiên dài đã hoàn tất; phụ đề trực tiếp cần được rà soát.';
          }
        });
        _revealSelectedVideo();
      }
    } catch (error) {
      await _closeLiveSession();
      if (mounted) setState(() => _error = 'Không thể lưu video: $error');
    } finally {
      if (mounted) {
        setState(() => _changingRecording = false);
        CaptureSessionNotification(
          _isRecording && _livePreviewEnabled,
        ).dispatch(context);
      }
    }
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
    if (_mode != 'visual_only' && _contextController.text.trim().isEmpty) {
      setState(
        () => _error = 'Chế độ có LLM cần một chủ đề/ngữ cảnh do bạn nhập.',
      );
      return;
    }
    if (_mode != 'visual_only' && !_acceptLlmRisk) {
      setState(
        () =>
            _error = 'Vui lòng xác nhận bạn sẽ kiểm tra kết quả hỗ trợ từ LLM.',
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
      final result = await LipReaderApi(widget.settings).transcribe(
        videoPath: video.path,
        mode: _mode,
        acceptLlmRisk: _acceptLlmRisk,
        contextHint: _contextController.text,
        onProgress: (progress) {
          if (mounted) setState(() => _uploadProgress = progress);
        },
        onStatus: (status) {
          if (mounted) setState(() => _processingStatus = status);
        },
      );
      await widget.history.add(result);
      if (!mounted) return;
      await context.push('/result', extra: result);
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
    if (_isRecording && _livePreviewEnabled) {
      return LiveCaptureLayout(
        header: const Wrap(
          spacing: 10,
          runSpacing: 4,
          crossAxisAlignment: WrapCrossAlignment.center,
          alignment: WrapAlignment.spaceBetween,
          children: [
            Icon(Icons.graphic_eq_rounded, color: AppColors.primary, size: 22),
            SizedBox(width: 10),
            Text(
              'Đang live',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            Text(
              'Chỉ dùng hình ảnh',
              style: TextStyle(fontSize: 12, color: AppColors.muted),
            ),
          ],
        ),
        preview: _buildCameraCard(),
        captions: _buildLiveDraft(),
        controls: _buildCaptureControls(),
      );
    }
    return SafeArea(
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          SliverAppBar(
            floating: true,
            title: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('LipLens', style: TextStyle(fontWeight: FontWeight.w800)),
                Text(
                  'Đọc lời nói qua chuyển động môi',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.muted,
                  ),
                ),
              ],
            ),
            actions: [
              IconButton(
                tooltip: 'Tuỳ chọn quay',
                onPressed: _isRecording || _changingRecording
                    ? null
                    : _showCaptureOptions,
                icon: const Icon(Icons.more_horiz_rounded),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            sliver: SliverList.list(
              children: [
                SizedBox(
                  height: (MediaQuery.sizeOf(context).height * .55).clamp(
                    340.0,
                    540.0,
                  ),
                  child: _buildCameraCard(),
                ),
                const SizedBox(height: 14),
                _buildCaptureControls(),
                const SizedBox(height: 10),
                const Row(
                  children: [
                    Icon(Icons.mic_none, size: 18),
                    SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        'Video lưu có âm thanh để đối chiếu. Phụ đề live chỉ dùng hình ảnh.',
                        style: TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                if (_changingRecording && !_isRecording) ...[
                  Row(
                    children: [
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: Text(_liveStatus)),
                    ],
                  ),
                  const SizedBox(height: 10),
                ],
                if (_error != null) ...[
                  _ErrorCard(message: _error!),
                  const SizedBox(height: 10),
                ],
                if (_livePreviewEnabled &&
                    (_isRecording || _liveWasActive)) ...[
                  const SizedBox(height: 10),
                  _buildLiveDraft(),
                ],
                if (_video != null) ...[
                  const SizedBox(height: 14),
                  _buildSelectedVideo(),
                  const SizedBox(height: 14),
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
    );
  }

  Widget _buildFullClipControls() {
    return Column(
      children: [
        _buildModeSelector(),
        const SizedBox(height: 14),
        TextField(
          controller: _contextController,
          maxLength: 100,
          enabled: !_submitting,
          decoration: InputDecoration(
            labelText: 'Chủ đề câu nói (không bắt buộc)',
            hintText: 'Ví dụ: hỏi đường, lớp học, bệnh viện…',
            counterText: '',
            helperText: _mode == 'visual_only'
                ? 'Chế độ thuần môi giữ nguyên kết quả nhận dạng, không sửa câu.'
                : 'LLM dùng ngữ cảnh này; kết quả sẽ hiện cạnh bản thuần môi.',
            prefixIcon: const Icon(Icons.subject_outlined),
          ),
        ),
        if (_mode != 'visual_only')
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _acceptLlmRisk,
            onChanged: _submitting
                ? null
                : (value) => setState(() => _acceptLlmRisk = value ?? false),
            title: const Text(
              'Tôi sẽ kiểm tra kết quả hỗ trợ từ LLM',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
            subtitle: const Text(
              'Kết quả thị giác gốc luôn được giữ riêng để đối chiếu.',
            ),
            controlAffinity: ListTileControlAffinity.leading,
          ),
        const SizedBox(height: 10),
        FilledButton.icon(
          onPressed: _submitting ? null : _submit,
          icon: _submitting
              ? const SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(Icons.auto_awesome_outlined),
          label: Text(
            _submitting
                ? _uploadProgress < 1
                      ? 'Đang tải ${(_uploadProgress * 100).round()}%'
                      : 'Đang xử lý…'
                : 'Đọc đoạn video này',
          ),
        ),
        if (_submitting && _uploadProgress >= 1) ...[
          const SizedBox(height: 8),
          Text(
            '$_processingStatus\nHãy giữ ứng dụng mở để tự động nhận kết quả khi hoàn tất.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.muted),
          ),
        ],
      ],
    );
  }

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
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: StatefulBuilder(
            builder: (context, updateSheet) => Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Tuỳ chọn quay',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                _buildLiveOption(onChanged: () => updateSheet(() {})),
                const SizedBox(height: 16),
                _buildTips(),
                const SizedBox(height: 14),
                const Text(
                  'Video được lưu có âm thanh để bạn đối chiếu. Phụ đề trực tiếp chỉ dùng hình ảnh.',
                  style: TextStyle(color: AppColors.muted),
                ),
              ],
            ),
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
    return Row(
      children: [
        if (!_isRecording)
          Expanded(
            child: OutlinedButton.icon(
              onPressed: _isRecording || _submitting || _changingRecording
                  ? null
                  : _pickVideo,
              icon: const Icon(Icons.video_library_outlined),
              label: const Text('Chọn video'),
            ),
          ),
        if (!_isRecording) const SizedBox(width: 12),
        Expanded(
          child: FilledButton.icon(
            style: _isRecording
                ? FilledButton.styleFrom(backgroundColor: AppColors.error)
                : null,
            onPressed:
                _camera?.value.isInitialized == true &&
                    !_submitting &&
                    !_changingRecording
                ? _toggleRecording
                : null,
            icon: Icon(
              _isRecording ? Icons.stop_rounded : Icons.fiber_manual_record,
            ),
            label: Text(
              _changingRecording
                  ? _isRecording
                        ? 'Đang kết thúc…'
                        : 'Đang chuẩn bị…'
                  : _isRecording
                  ? 'Kết thúc phiên'
                  : _livePreviewEnabled
                  ? 'Bắt đầu live'
                  : 'Bắt đầu quay',
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildLiveOption({VoidCallback? onChanged}) {
    return Card(
      child: SwitchListTile(
        value: _livePreviewEnabled,
        onChanged: _isRecording || _submitting || _changingRecording
            ? null
            : (value) {
                setState(() {
                  _livePreviewEnabled = value;
                  if (!value) {
                    _liveWasActive = false;
                    _liveTranscript = '';
                    _liveStableTranscript = '';
                    _liveStatus = 'Sẵn sàng tạo phụ đề trực tiếp';
                  }
                });
                onChanged?.call();
              },
        secondary: const Icon(
          Icons.subtitles_outlined,
          color: AppColors.primary,
        ),
        title: const Text(
          'Phụ đề trực tiếp',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: const Text(
          'Tự chốt câu khi bạn ngừng nói. Mỗi phiên tối đa 5 phút.',
        ),
      ),
    );
  }

  Widget _buildLiveDraft() => SizedBox(
    height: 270,
    child: LiveCaptionPanel(
      transcript: _liveTranscript,
      committed: _liveStableTranscript,
      provisional: _liveProvisional,
      status: _liveStatus,
      unavailable:
          _liveWarning != null ||
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
          }.contains(_liveState),
      captureFps: _liveFps,
      elapsedMs: _liveElapsedMs,
      waitingForCaption: {'speaking', 'pausing'}.contains(_liveState),
      unavailableWindows:
          (_liveEvidence['unavailable_windows'] as num?)?.toInt() ?? 0,
    ),
  );

  Widget _buildSelectedVideo() {
    final video = _video!;
    final name = video.name.isEmpty ? 'video.mp4' : video.name;
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
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: AppColors.muted),
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Bỏ video',
              onPressed: _submitting
                  ? null
                  : () => setState(() => _video = null),
              icon: const Icon(Icons.close_rounded),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildModeSelector() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Chế độ xử lý',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            RadioGroup<String>(
              groupValue: _mode,
              onChanged: (value) {
                if (_submitting || value == null) return;
                setState(() {
                  _mode = value;
                  if (value == 'visual_only') _acceptLlmRisk = false;
                });
              },
              child: const Column(
                children: [
                  _ModeTile(
                    value: 'visual_only',
                    icon: Icons.visibility_outlined,
                    title: 'Thuần chuyển động môi',
                    detail: 'Auto-AVSR gốc · không LLM · mặc định',
                  ),
                  _ModeTile(
                    value: 'context_select',
                    icon: Icons.alt_route_rounded,
                    title: 'Ngữ cảnh giới hạn',
                    detail: 'LLM chỉ được chọn trong các câu N-best có sẵn',
                  ),
                  _ModeTile(
                    value: 'llm_assist',
                    icon: Icons.auto_awesome_outlined,
                    title: 'Trợ lý diễn giải',
                    detail:
                        'Diễn giải tự nhiên · luôn giữ kết quả thị giác gốc',
                    last: true,
                  ),
                ],
              ),
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
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
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

class _ModeTile extends StatelessWidget {
  const _ModeTile({
    required this.value,
    required this.icon,
    required this.title,
    required this.detail,
    this.last = false,
  });

  final String value;
  final IconData icon;
  final String title;
  final String detail;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : 6),
      child: RadioListTile<String>(
        value: value,
        contentPadding: EdgeInsets.zero,
        secondary: Icon(icon, color: AppColors.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Text(detail),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFE9E7),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: AppColors.error),
          const SizedBox(width: 10),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}
