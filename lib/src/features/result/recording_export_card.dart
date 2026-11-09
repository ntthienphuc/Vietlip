import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../data/recording_export.dart';

class RecordingExportCard extends StatefulWidget {
  const RecordingExportCard({required this.path, super.key});
  final String path;

  @override
  State<RecordingExportCard> createState() => _RecordingExportCardState();
}

class _RecordingExportCardState extends State<RecordingExportCard> {
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final saved = await RecordingExport.save(widget.path);
      if (saved && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Đã lưu bản MP4 vào nơi bạn chọn')),
        );
      }
    } on PlatformException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error.code == 'export_unavailable'
                ? 'Không mở được bản ghi. Video có thể đã bị xóa hoặc di chuyển.'
                : 'Chưa lưu được video. Hãy kiểm tra dung lượng và thử lại.',
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Chưa xuất được video. Hãy thử lại.')),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      return const SizedBox.shrink();
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Video của phiên',
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
            ),
            const SizedBox(height: 6),
            const Text(
              'Lưu bản MP4 có âm thanh để xem lại hoặc chia sẻ. '
              'Bản gốc vẫn được giữ trong ứng dụng.',
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save_alt_rounded),
              label: Text(_saving ? 'Đang lưu…' : 'Lưu video ra máy'),
            ),
          ],
        ),
      ),
    );
  }
}
