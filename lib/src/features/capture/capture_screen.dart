import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../data/camera_frame_encoder.dart';
import '../../data/history_repository.dart';
import '../../data/live_lip_session.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';

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
  Duration _recordedFor = Duration.zero;
  bool _initializing = true;
  bool _submitting = false;
  double _uploadProgress = 0;
  String _processingStatus = 'Đang chuẩn bị video…';
  String? _error;
  String _mode = 'visual_only';
  bool _acceptLlmRisk = false;
  bool _livePreviewEnabled = true;
  bool _liveWasActive = false;
  bool _encodingLiveFrame = false;
  DateTime? _lastLiveFrameAt;
  LiveLipSession? _liveSession;
  StreamSubscription<LiveLipUpdate>? _liveSubscription;
  String _liveTranscript = '';
  String _liveStableTranscript = '';
  String _liveStatus = 'Sẵn sàng tạo phụ đề trực tiếp';

  bool get _isRecording => _camera?.value.isRecordingVideo == true;
  Duration get _activeMaxDuration =>
      _livePreviewEnabled ? _maxLiveDuration : _maxFullClipDuration;
  bool get _canRunFullClip =>
      _recordedFor == Duration.zero || _recordedFor <= _maxFullClipDuration;

  String get _liveOverlayText {
    final words = _liveTranscript.trim().split(RegExp(r'\s+'));
    if (_liveTranscript.trim().isEmpty) return _liveStatus;
    const visibleWords = 18;
    return words.length <= visibleWords
        ? words.join(' ')
        : '…${words.sublist(words.length - visibleWords).join(' ')}';
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_initializeCamera());
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
      if (!mounted || !_scrollController.hasClients) return;
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
      _timer?.cancel();
      unawaited(_closeLiveSession());
      unawaited(_camera?.dispose());
      _camera = null;
    } else if (state == AppLifecycleState.resumed && _camera == null) {
      unawaited(_initializeCamera());
    }
  }

  Future<void> _initializeCamera([CameraDescription? requested]) async {
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
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );
      await controller.initialize();
      await controller.prepareForVideoRecording();
      await _camera?.dispose();
      _camera = controller;
    } on CameraException catch (error) {
      _error = error.code == 'CameraAccessDenied'
          ? 'Bạn cần cấp quyền camera để quay khuôn mặt.'
          : 'Không mở được camera: ${error.description ?? error.code}';
    } catch (error) {
      _error = error.toString();
    } finally {
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
    if (controller == null || !controller.value.isInitialized || _submitting) {
      return;
    }
    if (_isRecording) {
      await _stopRecording();
      return;
    }
    try {
      final liveSession = await _openLiveSession(controller);
      await controller.startVideoRecording(
        onAvailable: liveSession == null ? null : _handleLiveFrame,
      );
      _timer?.cancel();
      setState(() {
        _video = null;
        _recordedFor = Duration.zero;
        _error = null;
        _liveWasActive = _livePreviewEnabled;
        _liveTranscript = '';
        _liveStableTranscript = '';
      });
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!mounted) return;
        final next = Duration(seconds: timer.tick);
        setState(() => _recordedFor = next);
        if (next >= _activeMaxDuration) unawaited(_stopRecording());
      });
    } catch (error) {
      await _closeLiveSession();
      if (mounted) setState(() => _error = 'Không thể bắt đầu quay: $error');
    }
  }

  Future<LiveLipSession?> _openLiveSession(CameraController controller) async {
    if (!_livePreviewEnabled) return null;
    if (!controller.supportsImageStreaming()) {
      if (mounted) {
        setState(
          () => _liveStatus =
              'Camera này không hỗ trợ phụ đề trực tiếp; video vẫn được lưu.',
        );
      }
      return null;
    }
    await _closeLiveSession();
    if (mounted) setState(() => _liveStatus = 'Đang kết nối phụ đề…');
    try {
      final session = LiveLipSession(widget.settings.apiUrl);
      await session.connect();
      _liveSession = session;
      _liveSubscription = session.updates.listen(_handleLiveUpdate);
      if (mounted) {
        setState(() => _liveStatus = 'Đang thu nhận chuyển động môi…');
      }
      return session;
    } catch (_) {
      if (mounted) {
        setState(
          () => _liveStatus =
              'Chưa kết nối được phụ đề; video vẫn được lưu bình thường.',
        );
      }
      return null;
    }
  }

  void _handleLiveUpdate(LiveLipUpdate update) {
    if (!mounted) return;
    setState(() {
      if (update.type == 'partial' ||
          update.type == 'segment_final' ||
          update.type == 'session_final') {
        _liveTranscript = update.transcript;
        _liveStableTranscript = update.stableTranscript;
        _liveStatus = update.type == 'session_final'
            ? 'Đã hoàn tất phụ đề của phiên'
            : update.device?.startsWith('cpu') == true
            ? 'Phụ đề từ CPU · đang tiếp tục cập nhật'
            : 'Phụ đề đang được cập nhật';
      } else if (update.type == 'ready') {
        _liveStatus = 'Đang thu nhận chuyển động môi…';
      } else if (update.message?.isNotEmpty == true) {
        _liveStatus = update.message!;
      }
    });
  }

  void _handleLiveFrame(CameraImage image) {
    final session = _liveSession;
    if (session == null || !session.isConnected || _encodingLiveFrame) return;
    final now = DateTime.now();
    if (_lastLiveFrameAt != null &&
        now.difference(_lastLiveFrameAt!) < const Duration(milliseconds: 125)) {
      return;
    }
    _lastLiveFrameAt = now;
    _encodingLiveFrame = true;
    final payload = copyCameraFrame(
      image,
      rotationDegrees: _camera?.description.sensorOrientation ?? 0,
    );
    unawaited(
      compute(encodeCameraFrame, payload)
          .then((jpeg) {
            if (jpeg != null) session.sendFrame(jpeg);
          })
          .catchError((Object _) {
            if (mounted) {
              setState(
                () => _liveStatus =
                    'Không nén được một khung hình; video vẫn tiếp tục được lưu.',
              );
            }
          })
          .whenComplete(() => _encodingLiveFrame = false),
    );
  }

  Future<String?> _closeLiveSession() async {
    final session = _liveSession;
    _liveSession = null;
    if (session != null) {
      for (var attempt = 0; attempt < 10 && _encodingLiveFrame; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
    }
    final finalTranscript = session == null ? null : await session.stop();
    await _liveSubscription?.cancel();
    _liveSubscription = null;
    _encodingLiveFrame = false;
    _lastLiveFrameAt = null;
    return finalTranscript;
  }

  Future<void> _stopRecording() async {
    final controller = _camera;
    if (controller == null || !controller.value.isRecordingVideo) return;
    _timer?.cancel();
    try {
      final video = await controller.stopVideoRecording();
      if (mounted && _livePreviewEnabled) {
        setState(() => _liveStatus = 'Đang hoàn tất phần phụ đề cuối…');
      }
      final finalTranscript = await _closeLiveSession();
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
    return SafeArea(
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          SliverAppBar(
            floating: true,
            title: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Đọc môi Việt',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                Text(
                  'Nhận dạng lời nói qua hình ảnh',
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
                tooltip: 'Đổi camera',
                onPressed: _flipCamera,
                icon: const Icon(Icons.cameraswitch_outlined),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            sliver: SliverList.list(
              children: [
                _buildSafetyNote(),
                const SizedBox(height: 14),
                _buildCameraCard(),
                const SizedBox(height: 14),
                _buildCaptureControls(),
                const SizedBox(height: 10),
                _buildLiveOption(),
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
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  _ErrorCard(message: _error!),
                ],
                const SizedBox(height: 18),
                _buildTips(),
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

  Widget _buildSafetyNote() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.warningSoft,
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.fact_check_outlined, color: AppColors.warning),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Hãy kiểm tra kết quả trước khi sử dụng. Nhiều âm tiếng Việt có '
              'chuyển động môi tương tự nhau.',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraCard() {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 3 / 4,
        child: ColoredBox(
          color: AppColors.ink,
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (_initializing)
                const Center(
                  child: CircularProgressIndicator(color: Colors.white),
                )
              else if (_camera?.value.isInitialized == true)
                CameraPreview(_camera!)
              else
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(28),
                    child: Text(
                      'Camera chưa sẵn sàng.\nBạn vẫn có thể chọn video có sẵn.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white),
                    ),
                  ),
                ),
              const IgnorePointer(
                child: CustomPaint(painter: _FaceGuidePainter()),
              ),
              Positioned(
                top: 14,
                left: 14,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 7,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.55),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: _isRecording
                              ? Colors.redAccent
                              : AppColors.primarySoft,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 7),
                      Text(
                        _isRecording ? _timerLabel : 'Giữ mặt trong khung',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Positioned(
                bottom: 18,
                left: 18,
                right: 18,
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 220),
                  child: _isRecording && _livePreviewEnabled
                      ? Semantics(
                          liveRegion: true,
                          label: 'Phụ đề trực tiếp: $_liveOverlayText',
                          child: Container(
                            key: ValueKey(_liveOverlayText),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 10,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.72),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(
                              _liveOverlayText,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                height: 1.25,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        )
                      : Text(
                          _livePreviewEnabled
                              ? 'Nhìn thẳng · đủ sáng · phụ đề liên tục đến 5 phút'
                              : 'Nhìn thẳng · đủ sáng · nói tự nhiên 2–45 giây',
                          key: const ValueKey('camera-guidance'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                            shadows: [
                              Shadow(blurRadius: 8, color: Colors.black),
                            ],
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCaptureControls() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _isRecording || _submitting ? null : _pickVideo,
            icon: const Icon(Icons.video_library_outlined),
            label: const Text('Chọn video'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: FilledButton.icon(
            style: _isRecording
                ? FilledButton.styleFrom(backgroundColor: AppColors.error)
                : null,
            onPressed: _camera?.value.isInitialized == true && !_submitting
                ? _toggleRecording
                : null,
            icon: Icon(
              _isRecording ? Icons.stop_rounded : Icons.fiber_manual_record,
            ),
            label: Text(_isRecording ? 'Dừng quay' : 'Bắt đầu quay'),
          ),
        ),
      ],
    );
  }

  Widget _buildLiveOption() {
    return Card(
      child: SwitchListTile(
        value: _livePreviewEnabled,
        onChanged: _isRecording || _submitting
            ? null
            : (value) => setState(() {
                _livePreviewEnabled = value;
                if (!value) {
                  _liveWasActive = false;
                  _liveTranscript = '';
                  _liveStableTranscript = '';
                  _liveStatus = 'Sẵn sàng tạo phụ đề trực tiếp';
                }
              }),
        secondary: const Icon(
          Icons.subtitles_outlined,
          color: AppColors.primary,
        ),
        title: const Text(
          'Phụ đề trực tiếp',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: const Text(
          'Nói liên tục tối đa 5 phút; nội dung được cập nhật và nối thành một bản ghi.',
        ),
      ),
    );
  }

  Widget _buildLiveDraft() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (_isRecording)
                const SizedBox.square(
                  dimension: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                const Icon(
                  Icons.fact_check_outlined,
                  size: 19,
                  color: AppColors.primary,
                ),
              const SizedBox(width: 9),
              Expanded(
                child: const Text(
                  'Nội dung đang nhận dạng',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              if (_liveTranscript.isNotEmpty)
                IconButton(
                  tooltip: 'Sao chép phụ đề',
                  onPressed: () async {
                    await Clipboard.setData(
                      ClipboardData(text: _liveTranscript),
                    );
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Đã sao chép phụ đề')),
                      );
                    }
                  },
                  icon: const Icon(Icons.copy_rounded),
                ),
            ],
          ),
          const SizedBox(height: 9),
          SelectableText(
            _liveTranscript.isEmpty ? '…' : _liveTranscript,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          if (_liveStableTranscript.isNotEmpty) ...[
            const SizedBox(height: 5),
            Text(
              'Đã ổn định: $_liveStableTranscript',
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 7),
          Text(_liveStatus, style: const TextStyle(color: AppColors.muted)),
        ],
      ),
    );
  }

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

class _FaceGuidePainter extends CustomPainter {
  const _FaceGuidePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final overlay = Paint()..color = Colors.black.withValues(alpha: 0.22);
    final guideRect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * 0.47),
      width: size.width * 0.72,
      height: size.height * 0.62,
    );
    final guide = RRect.fromRectAndRadius(
      guideRect,
      Radius.circular(size.width * 0.36),
    );
    final full = Path()..addRect(Offset.zero & size);
    final hole = Path()..addRRect(guide);
    canvas.drawPath(
      Path.combine(PathOperation.difference, full, hole),
      overlay,
    );
    canvas.drawRRect(
      guide,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.9)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );

    final mouthCenter = Offset(size.width / 2, size.height * 0.60);
    canvas.drawOval(
      Rect.fromCenter(
        center: mouthCenter,
        width: size.width * 0.32,
        height: size.height * 0.10,
      ),
      Paint()
        ..color = AppColors.accent.withValues(alpha: 0.95)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
