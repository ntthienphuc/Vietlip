import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/history_repository.dart';
import '../../models/transcription_result.dart';
import '../../theme/app_theme.dart';
import '../../widgets/status_notice.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({required this.history, super.key});

  final HistoryRepository history;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late Future<List<TranscriptionResult>> _future = widget.history.list();

  @override
  void initState() {
    super.initState();
    widget.history.addListener(_reload);
  }

  @override
  void didUpdateWidget(covariant HistoryScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.history != widget.history) {
      oldWidget.history.removeListener(_reload);
      widget.history.addListener(_reload);
      _future = widget.history.list();
    }
  }

  @override
  void dispose() {
    widget.history.removeListener(_reload);
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _future = widget.history.list();
    });
    try {
      await _future;
    } catch (_) {
      // FutureBuilder renders the recoverable error state.
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Scaffold(
        appBar: AppBar(
          title: const Text(
            'Lịch sử',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          actions: [
            IconButton(
              tooltip: 'Xóa lịch sử',
              onPressed: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Xóa lịch sử?'),
                    content: const Text(
                      'Các bản phụ đề trong lịch sử trên điện thoại sẽ bị xóa. Video đã lưu vẫn được giữ lại.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Hủy'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Xóa lịch sử'),
                      ),
                    ],
                  ),
                );
                if (confirmed == true) {
                  await widget.history.clear();
                }
              },
              icon: const Icon(Icons.delete_outline),
            ),
          ],
        ),
        body: FutureBuilder<List<TranscriptionResult>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Padding(
                padding: const EdgeInsets.all(20),
                child: StatusNotice(
                  title: 'Chưa mở được lịch sử',
                  detail: 'Hãy thử tải lại các phiên đã lưu trên điện thoại.',
                  error: true,
                  action: 'Tải lại lịch sử',
                  onAction: _reload,
                ),
              );
            }
            if (!snapshot.hasData) {
              return Center(child: CircularProgressIndicator());
            }
            final items = snapshot.data!;
            if (items.isEmpty) {
              return const _EmptyHistory();
            }
            return RefreshIndicator(
              onRefresh: _reload,
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                itemCount: items.length + 1,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Padding(
                      padding: const EdgeInsets.only(top: 4, bottom: 18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${items.length} phiên đã lưu',
                            style: const TextStyle(
                              fontSize: 26,
                              letterSpacing: -.7,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          const Text(
                            'Xem lại những lời đã nói.',
                            style: TextStyle(
                              color: AppColors.muted,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                  final item = items[index - 1];
                  return Card(
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      leading: Container(
                        width: 44,
                        height: 48,
                        decoration: BoxDecoration(
                          color: AppColors.primarySoft,
                          borderRadius: BorderRadius.circular(13),
                        ),
                        child: const Icon(
                          Icons.closed_caption_outlined,
                          color: AppColors.primary,
                          size: 22,
                        ),
                      ),
                      title: Text(
                        item.transcript.isEmpty
                            ? 'Không đọc được câu'
                            : item.transcript,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w500,
                          fontSize: 14,
                          height: 1.5,
                        ),
                      ),
                      subtitle: Text(
                        '${item.modelId.startsWith('QA-prerecorded-') ? 'Kiểm thử phát lại · ' : ''}'
                        '${_formatDate(item.createdAt)}'
                        '${item.sentences.any((s) => s.rewrite != null) ? ' · Gợi ý theo câu' : ''}'
                        '${item.rewrite?.hasText == true
                            ? ' · Có gợi ý'
                            : item.rewrite?.pending == true
                            ? ' · Đang soạn gợi ý'
                            : ''}',
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppColors.muted,
                          height: 2.1,
                        ),
                      ),
                      trailing: const Icon(Icons.chevron_right_rounded),
                      onTap: () => context.push('/result', extra: item),
                    ),
                  );
                },
              ),
            );
          },
        ),
      ),
    );
  }

  String _formatDate(DateTime value) {
    final local = value.toLocal();
    return '${local.hour.toString().padLeft(2, '0')}:'
        '${local.minute.toString().padLeft(2, '0')} '
        '${local.day}/${local.month}/${local.year}';
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.history_toggle_off,
              size: 58,
              color: AppColors.primary,
            ),
            const SizedBox(height: 24),
            const Text(
              'Chưa có bản đọc môi nào',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              'Kết thúc một phiên đọc môi để lưu phụ đề và xem lại tại đây.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => context.go('/read'),
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('Bắt đầu đọc môi'),
            ),
          ],
        ),
      ),
    );
  }
}
