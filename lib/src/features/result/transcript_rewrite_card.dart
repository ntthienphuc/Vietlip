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
                    review.pending ? 'Đang soạn gợi ý…' : 'Gợi ý câu',
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
                      const SnackBar(content: Text('Đã sao chép gợi ý')),
                    );
                  }
                },
                icon: const Icon(Icons.copy_outlined, size: 18),
                label: const Text('Sao chép gợi ý'),
              ),
              const SizedBox(height: 8),
              Text(
                review.status == 'unchanged'
                    ? 'Gợi ý trùng với phụ đề gốc.'
                    : 'Đối chiếu gợi ý với phụ đề gốc để kiểm tra ý câu nói.',
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
            ] else
              Text(
                review.pending
                    ? 'Phụ đề gốc đã lưu. Bạn có thể xem lại gợi ý trong Lịch sử.'
                    : 'Chưa có gợi ý cho câu này. Bạn vẫn có thể xem phụ đề gốc.',
                style: const TextStyle(color: AppColors.muted, height: 1.5),
              ),
          ],
        ),
      ),
    );
  }
}
