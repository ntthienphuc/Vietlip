import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../models/transcription_result.dart';
import '../../theme/app_theme.dart';
import 'recording_export_card.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({required this.result, super.key});

  final TranscriptionResult result;

  @override
  Widget build(BuildContext context) {
    final quality = Map<String, dynamic>.from(
      result.diagnostics['quality'] as Map? ?? const {},
    );
    final warnings =
        (result.diagnostics['warnings'] as List<dynamic>? ?? const [])
            .map((item) => item.toString())
            .toList();
    final llmDiagnostics = Map<String, dynamic>.from(
      result.diagnostics['llm'] as Map? ?? const {},
    );
    final consensus = Map<String, dynamic>.from(
      result.diagnostics['nbest_consensus'] as Map? ?? const {},
    );
    final llmDidNotProduceResult =
        result.processingMode != 'visual_only' &&
        result.assistedTranscript?.isNotEmpty != true;

    return Scaffold(
      appBar: AppBar(title: const Text('Bản đọc môi')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.warningSoft,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Row(
              children: [
                Icon(Icons.rate_review_outlined, color: AppColors.warning),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Cần xem lại trước khi sử dụng',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          if (llmDidNotProduceResult) ...[
            Card(
              color: AppColors.warningSoft,
              child: ListTile(
                leading: const Icon(
                  Icons.info_outline,
                  color: AppColors.warning,
                ),
                title: const Text(
                  'Không có bản hỗ trợ LLM',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  llmDiagnostics['message']?.toString() ??
                      'LLM chưa sẵn sàng; bản thuần chuyển động môi vẫn hợp lệ.',
                ),
              ),
            ),
            const SizedBox(height: 14),
          ],
          if (result.assistedTranscript?.isNotEmpty == true) ...[
            Card(
              color: AppColors.primarySoft,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(
                          Icons.auto_awesome,
                          color: AppColors.primary,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          result.processingMode == 'context_select'
                              ? 'LLM chọn theo ngữ cảnh'
                              : 'LLM diễn giải',
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            color: AppColors.primary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    SelectableText(
                      result.assistedTranscript!,
                      style: const TextStyle(
                        fontSize: 24,
                        height: 1.35,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    if (result.riskNotice != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        result.riskNotice!,
                        style: const TextStyle(
                          color: AppColors.error,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                    if (llmDiagnostics['model'] != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        _llmRuntimeLabel(llmDiagnostics),
                        style: const TextStyle(
                          color: AppColors.muted,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                    if (llmDiagnostics['reason']
                            ?.toString()
                            .trim()
                            .isNotEmpty ==
                        true) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Lý do LLM: ${llmDiagnostics['reason']}',
                        style: const TextStyle(color: AppColors.muted),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),
          ],
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Bản thuần chuyển động môi',
                    style: TextStyle(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  SelectableText(
                    result.transcript.isEmpty
                        ? 'Không đọc được câu rõ ràng.'
                        : result.transcript,
                    style: const TextStyle(
                      fontSize: 27,
                      height: 1.35,
                      fontWeight: FontWeight.w800,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: result.transcript.isEmpty
                        ? null
                        : () async {
                            await Clipboard.setData(
                              ClipboardData(text: result.transcript),
                            );
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Đã sao chép kết quả'),
                              ),
                            );
                          },
                    icon: const Icon(Icons.copy_outlined),
                    label: const Text('Sao chép'),
                  ),
                ],
              ),
            ),
          ),
          if (result.diagnostics['video_path'] is String &&
              (result.diagnostics['video_path'] as String).isNotEmpty) ...[
            const SizedBox(height: 14),
            RecordingExportCard(
              path: result.diagnostics['video_path'] as String,
            ),
          ],
          if (result.consensusTranscript?.isNotEmpty == true &&
              result.consensusTranscript != result.transcript) ...[
            const SizedBox(height: 14),
            Card(
              color: const Color(0xFFF0F7F5),
              child: ListTile(
                leading: const Icon(
                  Icons.hub_outlined,
                  color: AppColors.primary,
                ),
                title: const Text(
                  'Gợi ý đồng thuận N-best',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  '${result.consensusTranscript}\nỨng viên trung tâm theo khoảng cách từ; không thay thế bản thị giác gốc.',
                ),
              ),
            ),
          ],
          if (result.alternatives.length > 1) ...[
            const SizedBox(height: 18),
            const Text(
              'Cách đọc khác',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            ...result.alternatives
                .skip(1)
                .where((item) => item.text.isNotEmpty)
                .take(5)
                .map(
                  (item) => Card(
                    child: ListTile(
                      leading: const Icon(Icons.alt_route_rounded),
                      title: Text(item.text),
                      subtitle: const Text(
                        'Ứng viên từ beam search · không phải xác suất',
                      ),
                    ),
                  ),
                ),
          ],
          const SizedBox(height: 18),
          const Text(
            'Thông tin xử lý',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _MetricChip(
                    icon: Icons.movie_outlined,
                    label: '${result.numFrames} khung hình',
                  ),
                  _MetricChip(
                    icon: Icons.timer_outlined,
                    label: _elapsedLabel(result.elapsedMs),
                  ),
                  if (quality['face_detection_ratio'] != null)
                    _MetricChip(
                      icon: Icons.face_outlined,
                      label:
                          'Bắt mặt ${((quality['face_detection_ratio'] as num) * 100).round()}%',
                    ),
                  if (quality['blur_score'] != null)
                    _MetricChip(
                      icon: Icons.blur_on_outlined,
                      label: 'Độ nét ${quality['blur_score']}',
                    ),
                  if (consensus['agrees_with_top1'] == true)
                    const _MetricChip(
                      icon: Icons.hub_outlined,
                      label: 'N-best đồng thuận',
                    ),
                ],
              ),
            ),
          ),
          if (warnings.isNotEmpty) ...[
            const SizedBox(height: 14),
            ...warnings.map(
              (warning) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.info_outline,
                      size: 20,
                      color: AppColors.warning,
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(warning)),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.replay_outlined),
            label: const Text('Quay một đoạn khác'),
          ),
          const SizedBox(height: 10),
          Text(
            'Chế độ: ${_modeLabel(result.processingMode)} · Mô hình: ${result.modelId} · Mã xử lý: ${result.requestId}',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: AppColors.muted),
          ),
        ],
      ),
    );
  }

  String _elapsedLabel(int milliseconds) {
    if (milliseconds < 1000) return '$milliseconds ms';
    return '${(milliseconds / 1000).toStringAsFixed(2)} giây';
  }

  String _llmRuntimeLabel(Map<String, dynamic> diagnostics) {
    final provider = diagnostics['provider']?.toString() ?? 'LLM';
    final model = diagnostics['model']?.toString() ?? '';
    final duration = diagnostics['total_duration_ms'] as num?;
    final timing = duration == null
        ? ''
        : ' · ${_elapsedLabel(duration.round())}';
    return '$provider · $model$timing';
  }

  String _modeLabel(String mode) => switch (mode) {
    'context_select' => 'Ngữ cảnh giới hạn',
    'llm_assist' => 'Trợ lý diễn giải',
    _ => 'Thuần chuyển động môi',
  };
}

class _MetricChip extends StatelessWidget {
  const _MetricChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: AppColors.primary),
          const SizedBox(width: 7),
          Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
