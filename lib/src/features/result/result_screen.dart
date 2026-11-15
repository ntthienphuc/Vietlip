import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../models/transcription_result.dart';
import '../../theme/app_theme.dart';
import 'recording_export_card.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({required this.result, super.key});
  final TranscriptionResult result;

  @override
  Widget build(BuildContext context) {
    final live = result.diagnostics['source'] == 'realtime';
    final incomplete = result.diagnostics['incomplete'] == true;
    final path = result.diagnostics['video_path'];
    final warnings = (result.diagnostics['warnings'] as List? ?? const [])
        .map((value) => value.toString())
        .where((value) => value.isNotEmpty);
    final date = result.createdAt.toLocal();
    return Scaffold(
      appBar: AppBar(title: const Text('Bản đọc môi')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 680),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
            children: [
              Text(
                '${date.day}/${date.month}/${date.year} lúc '
                '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}',
                style: const TextStyle(color: AppColors.muted, fontSize: 14),
              ),
              const SizedBox(height: 16),
              Card(
                color: AppColors.caption,
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Row(
                        children: [
                          Icon(
                            Icons.closed_caption_outlined,
                            color: AppColors.accent,
                            size: 22,
                          ),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Phụ đề',
                              style: TextStyle(
                                color: AppColors.captionMuted,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      SelectableText(
                        result.transcript.isEmpty
                            ? 'Chưa đọc được nội dung'
                            : result.transcript,
                        style: const TextStyle(
                          fontSize: 26,
                          height: 1.5,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 20),
                      if (result.transcript.isEmpty)
                        const Text(
                          'Thử lại ở nơi đủ sáng, giữ miệng rõ trong khung hình và nói từng câu ngắn.',
                          style: TextStyle(
                            color: AppColors.captionMuted,
                            height: 1.5,
                          ),
                        )
                      else
                        OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: const BorderSide(color: Color(0xFF627393)),
                          ),
                          onPressed: () async {
                            await Clipboard.setData(
                              ClipboardData(text: result.transcript),
                            );
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Đã sao chép phụ đề'),
                                ),
                              );
                            }
                          },
                          icon: const Icon(Icons.copy_outlined, size: 20),
                          label: const Text('Sao chép phụ đề'),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.info_outline_rounded,
                    size: 18,
                    color: incomplete ? AppColors.warning : AppColors.muted,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      incomplete
                          ? 'Phiên bị gián đoạn. Phụ đề có thể thiếu nội dung.'
                          : 'Phụ đề tự động có thể sai. Hãy kiểm tra lại khi sử dụng.',
                      style: const TextStyle(
                        color: AppColors.muted,
                        height: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
              if (path is String && path.isNotEmpty) ...[
                const SizedBox(height: 24),
                RecordingExportCard(path: path),
              ],
              const SizedBox(height: 16),
              ExpansionTile(
                tilePadding: const EdgeInsets.symmetric(horizontal: 4),
                childrenPadding: const EdgeInsets.fromLTRB(4, 0, 4, 16),
                title: const Text(
                  'Thông tin phiên',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: SelectableText(
                      '${live ? 'Thời lượng phiên' : 'Thời gian xử lý'}: ${_elapsedLabel(result.elapsedMs)}\n'
                      '${result.numFrames} khung hình\n'
                      'Mô hình: ${result.modelId}\nMã phiên: ${result.requestId}'
                      '${warnings.isEmpty ? '' : '\n\n${warnings.join('\n')}'}',
                      style: const TextStyle(
                        fontSize: 13,
                        height: 1.6,
                        color: AppColors.muted,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => context.go('/read'),
                icon: const Icon(Icons.center_focus_strong_outlined),
                label: const Text('Đọc phiên mới'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _elapsedLabel(int milliseconds) {
    if (milliseconds < 1000) return '$milliseconds ms';
    return '${(milliseconds / 1000).toStringAsFixed(2)} giây';
  }
}
