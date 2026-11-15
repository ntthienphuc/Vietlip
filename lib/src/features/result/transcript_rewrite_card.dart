import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/reading_method.dart';
import '../../models/transcript_rewrite.dart';
import '../../theme/app_theme.dart';

class TranscriptRewriteCard extends StatefulWidget {
  const TranscriptRewriteCard({required this.review, super.key});
  final TranscriptRewrite review;
  @override
  State<TranscriptRewriteCard> createState() => _TranscriptRewriteCardState();
}

class _TranscriptRewriteCardState extends State<TranscriptRewriteCard> {
  Timer? _deadline;
  @override
  void initState() {
    super.initState();
    _watch();
  }

  @override
  void didUpdateWidget(covariant TranscriptRewriteCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    _watch();
  }

  void _watch() {
    _deadline?.cancel();
    if (widget.review.pending) {
      final remaining =
          const Duration(seconds: 40) -
          DateTime.now().difference(widget.review.startedAt!);
      _deadline = Timer(remaining, () {
        if (mounted) setState(() {});
      });
    }
  }

  @override
  void dispose() {
    _deadline?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final review = widget.review;
    final method = ReadingMethod.parse(review.method);
    return Card(
      color: AppColors.primarySoft,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.auto_awesome_outlined,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    review.pending ? 'AI đang xem lại câu…' : 'Đề xuất AI',
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 17,
                    ),
                  ),
                ),
                if (review.pending)
                  const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              method.label,
              style: const TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 14),
            if (review.hasText) ...[
              SelectableText(
                review.text,
                style: const TextStyle(
                  fontSize: 22,
                  height: 1.5,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: review.text));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Đã sao chép bản AI')),
                    );
                  }
                },
                icon: const Icon(Icons.copy_outlined, size: 18),
                label: const Text('Sao chép bản AI'),
              ),
              const SizedBox(height: 8),
              Text(
                review.status == 'unchanged'
                    ? 'AI giữ nguyên nội dung. Hãy đối chiếu với bản gốc.'
                    : 'AI có thể đổi ý câu nói. Hãy đối chiếu với bản gốc.',
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
              if (review.modelId != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Text(
                    '${review.modelId} · ${(review.elapsedMs / 1000).toStringAsFixed(1)} giây',
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 12,
                    ),
                  ),
                ),
            ] else
              Text(
                review.pending
                    ? 'Bạn có thể rời màn hình này. Bản sửa sẽ được cập nhật trong Lịch sử; bản gốc đã lưu.'
                    : review.message ??
                          'AI chưa hoàn tất. Bản phụ đề gốc đã được giữ lại.',
                style: const TextStyle(color: AppColors.muted, height: 1.5),
              ),
          ],
        ),
      ),
    );
  }
}
