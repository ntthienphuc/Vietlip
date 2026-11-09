import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../theme/app_theme.dart';

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
  });
  final String transcript, committed, provisional, status;
  final bool unavailable;
  final double? captureFps;
  final int? elapsedMs;
  final int unavailableWindows;
  final bool waitingForCaption;

  String tail(String text, int count) {
    final words = text.trim().split(RegExp(r'\s+'));
    return words.length <= count
        ? text
        : '… ${words.skip(words.length - count).join(' ')}';
  }

  @override
  Widget build(BuildContext context) {
    final accent = unavailable ? AppColors.error : AppColors.primary;
    final fixed = committed.isEmpty && provisional.isEmpty
        ? transcript
        : committed;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 6, 12, 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppColors.ink.withValues(alpha: .035),
            blurRadius: 20,
            offset: const Offset(0, 6),
          ),
        ],
        border: Border.all(
          color: unavailable
              ? AppColors.error
              : AppColors.primary.withValues(alpha: .2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                unavailable
                    ? Icons.info_outline
                    : Icons.closed_caption_outlined,
                size: 20,
                color: accent,
              ),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Phụ đề trực tiếp',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
              ),
              if (captureFps != null ||
                  elapsedMs != null ||
                  unavailableWindows > 0)
                IconButton(
                  tooltip: 'Thông tin phiên',
                  onPressed: () => _showDiagnostics(context),
                  icon: const Icon(Icons.info_outline_rounded, size: 19),
                ),
              IconButton(
                tooltip: 'Xem toàn bộ phụ đề',
                onPressed: transcript.isEmpty
                    ? null
                    : () => _showTranscript(context),
                icon: const Icon(Icons.open_in_full, size: 18),
              ),
            ],
          ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: .07),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              status,
              style: TextStyle(
                color: accent,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 10),
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
                            ? unavailable
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
                            color: AppColors.primary,
                            decoration: TextDecoration.underline,
                            decorationStyle: TextDecorationStyle.dotted,
                          ),
                        ),
                    ],
                  ),
                  style: TextStyle(
                    fontSize: 24,
                    height: 1.45,
                    fontWeight: FontWeight.w600,
                    color: unavailable ? AppColors.muted : AppColors.ink,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            unavailable
                ? transcript.isEmpty
                      ? 'Phụ đề sẽ tiếp tục khi hình rõ trở lại.'
                      : 'Phần đã nhận trước đó được giữ lại.'
                : provisional.isNotEmpty
                ? 'Chữ gạch dưới đang được cập nhật.'
                : 'Phụ đề tự động · cần kiểm tra lại.',
            style: const TextStyle(fontSize: 12, color: AppColors.muted),
          ),
        ],
      ),
    );
  }

  void _showDiagnostics(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Thông tin phiên',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 16),
              if (captureFps != null)
                Text('Hình ${captureFps!.toStringAsFixed(0)} fps'),
              if (elapsedMs != null)
                Text(
                  'Xử lý cửa sổ ${(elapsedMs! / 1000).toStringAsFixed(1)} s',
                ),
              Text('$unavailableWindows lượt chưa đọc được'),
              const SizedBox(height: 12),
              const Text(
                'Thời gian xử lý cửa sổ không phải tổng thời gian chờ phụ đề.',
                style: TextStyle(color: AppColors.muted),
              ),
            ],
          ),
        ),
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
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
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
