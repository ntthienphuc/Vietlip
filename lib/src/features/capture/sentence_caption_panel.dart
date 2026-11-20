import 'dart:async';
import 'package:flutter/material.dart';
import '../../models/live_sentence.dart';
import '../../models/reading_method.dart';
import '../../data/live_sentence_recovery.dart';
import '../../theme/app_theme.dart';
import '../../../shared/signova_style.dart';

/// Each raw/AI pair moves together. A late response never replaces a newer turn.
class SentenceCaptionPanel extends StatelessWidget {
  const SentenceCaptionPanel({
    super.key,
    required this.sentences,
    required this.draft,
    required this.provider,
    required this.status,
    this.idle = false,
    this.controller,
  });
  final List<LiveSentence> sentences;
  final String draft, status;
  final AiProvider provider;
  final bool idle;
  final LiveSentenceRecovery? controller;

  @override
  Widget build(BuildContext context) {
    final pending = sentences.where((s) => s.pending).length;
    return SignovaPanel(
      padding: const EdgeInsets.fromLTRB(14, 6, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const SignovaIconBadge(Icons.auto_awesome_rounded, size: 28),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Phụ đề và gợi ý',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Flexible(
                child: Text(
                  provider.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: AppColors.accent, fontSize: 11),
                ),
              ),
              IconButton(
                tooltip: 'Xem các câu trong phiên',
                onPressed: sentences.isEmpty ? null : () => _showAll(context),
                icon: Icon(
                  Icons.open_in_full_rounded,
                  size: 17,
                  color: sentences.isEmpty
                      ? AppColors.captionMuted
                      : AppColors.ink,
                ),
              ),
            ],
          ),
          if (pending > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: const LinearProgressIndicator(
                  minHeight: 2,
                  color: AppColors.accent,
                  backgroundColor: Color(0xffdce8f3),
                ),
              ),
            ),
          Expanded(
            child: ListView.builder(
              key: const ValueKey('sentence-pairs'),
              reverse: true,
              itemCount:
                  sentences.length +
                  (draft.isNotEmpty || sentences.isEmpty ? 1 : 0),
              itemBuilder: (context, index) {
                final hasDraft = draft.isNotEmpty || sentences.isEmpty;
                if (hasDraft && index == 0) {
                  return _DraftPair(draft: draft, idle: idle);
                }
                final sentence =
                    sentences[sentences.length -
                        1 -
                        index +
                        (hasDraft ? 1 : 0)];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: SentencePairCard(sentence: sentence),
                );
              },
            ),
          ),
          const SizedBox(height: 9),
          Text(
            pending > 0
                ? 'Đang soạn gợi ý cho $pending câu…'
                : idle
                ? 'Gợi ý xuất hiện sau mỗi câu.'
                : status,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.accent,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  void _showAll(BuildContext context) => showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) => SafeArea(
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * .75,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Các câu trong phiên',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 23),
              ),
              const SizedBox(height: 14),
              Expanded(
                child: controller == null
                    ? _allPairs(sentences)
                    : ListenableBuilder(
                        listenable: controller!,
                        builder: (context, _) =>
                            _allPairs(controller!.sentences),
                      ),
              ),
            ],
          ),
        ),
      ),
    ),
  );

  Widget _allPairs(List<LiveSentence> rows) => ListView(
    children: [
      for (final sentence in rows)
        Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: SentencePairCard(sentence: sentence),
        ),
    ],
  );
}

class SentencePairCard extends StatefulWidget {
  const SentencePairCard({super.key, required this.sentence});
  final LiveSentence sentence;
  @override
  State<SentencePairCard> createState() => _SentencePairCardState();
}

class _SentencePairCardState extends State<SentencePairCard> {
  Timer? _deadline;
  LiveSentence get sentence => widget.sentence;
  @override
  void initState() {
    super.initState();
    _watch();
  }

  @override
  void didUpdateWidget(covariant SentencePairCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    _watch();
  }

  void _watch() {
    _deadline?.cancel();
    final review = sentence.rewrite;
    if (review?.pending == true) {
      final remaining =
          const Duration(seconds: 40) -
          DateTime.now().difference(review!.startedAt!);
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
    final review = sentence.rewrite;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xffeef4ff),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'PHỤ ĐỀ GỐC · CÂU ${sentence.number}',
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.captionMuted,
                  fontWeight: FontWeight.w600,
                  letterSpacing: .5,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                sentence.raw,
                style: const TextStyle(
                  fontSize: 20,
                  height: 1.45,
                  color: AppColors.ink,
                ),
              ),
            ],
          ),
        ),
        if (review != null) ...[
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFE6F5EF),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.auto_awesome_rounded,
                      size: 13,
                      color: AppColors.success,
                    ),
                    const SizedBox(width: 6),
                    const Expanded(
                      child: Text(
                        'GỢI Ý CÂU',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppColors.success,
                          letterSpacing: .4,
                        ),
                      ),
                    ),
                    if (sentence.pending)
                      const SizedBox.square(
                        dimension: 13,
                        child: CircularProgressIndicator(
                          strokeWidth: 1.5,
                          color: AppColors.success,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 5),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    sentence.pending
                        ? 'Đang soạn gợi ý…'
                        : review.hasText
                        ? review.text
                        : (review.message ?? 'Chưa có gợi ý cho câu này.'),
                    style: TextStyle(
                      fontSize: review.hasText ? 22 : 15,
                      fontWeight: review.hasText
                          ? FontWeight.w600
                          : FontWeight.w400,
                      height: 1.45,
                      color: AppColors.ink,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _DraftPair extends StatelessWidget {
  const _DraftPair({required this.draft, required this.idle});
  final String draft;
  final bool idle;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(6, 2, 6, 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'PHỤ ĐỀ GỐC',
              style: TextStyle(
                color: AppColors.captionMuted,
                fontSize: 10,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 7),
            Text(
              draft.isEmpty
                  ? idle
                        ? 'Lời bạn nói sẽ\nhiện ở đây.'
                        : 'Đang chờ câu đầu tiên…'
                  : draft,
              style: const TextStyle(
                fontSize: 23,
                height: 1.4,
                color: AppColors.ink,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFE6F5EF),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'GỢI Ý CÂU',
              style: TextStyle(
                color: AppColors.success,
                fontSize: 10,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              idle
                  ? 'Gợi ý sẽ hiện ở đây.'
                  : 'Gợi ý sẽ hiện sau khi bạn ngừng nói.',
              style: const TextStyle(
                fontSize: 15,
                height: 1.45,
                color: AppColors.ink,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}
