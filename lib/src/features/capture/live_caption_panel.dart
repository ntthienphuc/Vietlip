import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../theme/app_theme.dart';
import '../../../shared/signova_style.dart';

String liveStatusLabel(String state, String? decoderState) {
  final quality = switch (state) {
    'waiting_for_face' => 'Chưa thấy mặt · nhìn thẳng vào camera',
    'multiple_faces' => 'Chỉ một người trong khung hình',
    'face_too_small' => 'Đưa khuôn mặt gần camera hơn',
    'poor_light' => 'Hình quá tối hoặc đang bị che',
    'look_straight' => 'Nhìn thẳng để thấy rõ chuyển động môi',
    'head_motion' => 'Giữ đầu ổn định một chút',
    'camera_stalled' => 'Chưa nhận được hình mới từ camera',
    'activity_unavailable' => 'Chưa theo dõi được môi · hãy thử lại',
    'network_stalled' => 'Mạng đang gián đoạn',
    'disconnected' => 'Mất kết nối · kết thúc và mở lại phiên',
    _ => null,
  };
  if (quality != null) return quality;
  if (decoderState == 'finalizing') return 'Đang chốt đoạn vừa nói…';
  return switch (state) {
    'speaking' => 'Đang thấy môi chuyển động · tiếp tục nói',
    'pausing' => 'Đang chờ khoảng ngừng để chốt đoạn…',
    _ => 'Sẵn sàng · bạn có thể nói câu tiếp theo',
  };
}

/// Keeps captions readable without covering the speaker's mouth.
class LiveCaptionPanel extends StatelessWidget {
  const LiveCaptionPanel({
    super.key,
    required this.transcript,
    required this.committed,
    required this.provisional,
    required this.status,
    required this.unavailable,
    this.captureFps,
    this.elapsedMs,
    this.unavailableWindows = 0,
    this.waitingForCaption = false,
    this.idle = false,
  });
  final String transcript, committed, provisional, status;
  final bool unavailable;
  final double? captureFps;
  final int? elapsedMs;
  final int unavailableWindows;
  final bool waitingForCaption;
  final bool idle;

  String tail(String text, int count) {
    final words = text.trim().split(RegExp(r'\s+'));
    return words.length <= count
        ? text
        : '… ${words.skip(words.length - count).join(' ')}';
  }

  @override
  Widget build(BuildContext context) {
    final accent = unavailable ? AppColors.error : AppColors.accent;
    final fixed = committed.isEmpty && provisional.isEmpty
        ? transcript
        : committed;
    return SignovaPanel(
      padding: const EdgeInsets.fromLTRB(20, 4, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SignovaIconBadge(
                unavailable
                    ? Icons.info_outline
                    : Icons.closed_caption_outlined,
                size: 28,
                color: accent,
              ),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Phụ đề trực tiếp',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Xem toàn bộ phụ đề',
                onPressed: transcript.isEmpty
                    ? null
                    : () => _showTranscript(context),
                icon: Icon(
                  Icons.open_in_full,
                  size: 17,
                  color: transcript.isEmpty
                      ? const Color(0xFF7383A2)
                      : AppColors.ink,
                ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Expanded(
            child: SingleChildScrollView(
              reverse: true,
              child: Semantics(
                liveRegion: true,
                child: Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: transcript.isEmpty
                            ? idle
                                  ? 'Phụ đề sẽ\nhiện ở đây.'
                                  : unavailable
                                  ? 'Chưa đủ hình rõ để đọc môi.'
                                  : waitingForCaption
                                  ? 'Đang đọc khẩu hình…'
                                  : 'Bắt đầu nói khi bạn sẵn sàng. Phụ đề sẽ hiện ở đây.'
                            : tail(fixed, 32),
                      ),
                      if (provisional.isNotEmpty && !unavailable)
                        TextSpan(
                          text: '${fixed.isEmpty ? '' : ' '}$provisional',
                          style: const TextStyle(
                            color: AppColors.accent,
                            decoration: TextDecoration.underline,
                            decorationStyle: TextDecorationStyle.dotted,
                          ),
                        ),
                    ],
                  ),
                  style: TextStyle(
                    fontSize: idle ? 26 : 24,
                    height: idle ? 1.3 : 1.4,
                    letterSpacing: -.6,
                    fontWeight: idle ? FontWeight.w700 : FontWeight.w600,
                    color: unavailable ? AppColors.captionMuted : AppColors.ink,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Icon(Icons.circle, size: 6, color: accent),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  idle
                      ? 'Bắt đầu phiên để chuyển khẩu hình thành chữ.'
                      : status,
                  style: TextStyle(fontSize: 12, height: 1.4, color: accent),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showTranscript(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * .65,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Bản ghi của phiên',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const Text(
                  'Phụ đề tự động · cần kiểm tra lại',
                  style: TextStyle(color: AppColors.muted),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: SingleChildScrollView(
                    child: SelectableText(
                      transcript,
                      style: const TextStyle(fontSize: 20, height: 1.5),
                    ),
                  ),
                ),
                FilledButton.icon(
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: transcript));
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Đã sao chép phụ đề')),
                      );
                    }
                  },
                  icon: const Icon(Icons.copy),
                  label: const Text('Sao chép bản ghi'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
