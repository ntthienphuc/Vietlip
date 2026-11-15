import 'package:flutter/material.dart';

import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../models/reading_method.dart';
import '../../theme/app_theme.dart';

class ReadingMethodSetting extends StatelessWidget {
  const ReadingMethodSetting({required this.settings, super.key});
  final SettingsController settings;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: settings,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Phương pháp phụ đề',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 8,
            ),
            leading: Icon(
              settings.readingMethod.usesAi
                  ? Icons.auto_awesome_outlined
                  : Icons.closed_caption_outlined,
              color: AppColors.primary,
            ),
            title: Text(
              settings.readingMethod.label,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              settings.readingMethod.subtitle,
              style: const TextStyle(color: AppColors.muted, height: 1.6),
            ),
            trailing: const Icon(Icons.tune_rounded),
            onTap: () => showModalBottomSheet<void>(
              context: context,
              useRootNavigator: true,
              showDragHandle: true,
              isScrollControlled: true,
              builder: (_) => _MethodPicker(settings: settings),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Live luôn hiện phụ đề gốc. Khi bật AI, bản sửa được tạo sau phiên '
          'và lưu riêng trong Lịch sử.',
          style: TextStyle(color: AppColors.muted, fontSize: 13, height: 1.6),
        ),
      ],
    ),
  );
}

class _MethodPicker extends StatefulWidget {
  const _MethodPicker({required this.settings});
  final SettingsController settings;
  @override
  State<_MethodPicker> createState() => _MethodPickerState();
}

class _MethodPickerState extends State<_MethodPicker> {
  Map<String, bool>? _configured;
  bool _loading = true, _saving = false;
  String? _notice;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    try {
      if (widget.settings.apiUrl.isEmpty) {
        throw const FormatException('Chưa có IP');
      }
      final methods = await LipReaderApi(widget.settings).rewriteMethods();
      if (mounted) setState(() => _configured = methods);
    } catch (_) {
      if (mounted) {
        setState(
          () => _notice =
              'Kết nối và cập nhật VietLip Server để dùng các phương pháp AI.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _select(ReadingMethod method) async {
    setState(() => _saving = true);
    try {
      await widget.settings.setReadingMethod(method);
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        setState(() {
          _notice = 'Chưa lưu được lựa chọn. Hãy thử lại.';
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SizedBox(
      height: MediaQuery.sizeOf(context).height * .78,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          const Text(
            'Chọn cách tạo phụ đề',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          const Text(
            'Lựa chọn áp dụng cho phiên tiếp theo.',
            style: TextStyle(color: AppColors.muted),
          ),
          const SizedBox(height: 16),
          for (final method in ReadingMethod.values) ...[
            _option(method),
            const SizedBox(height: 10),
          ],
          if (_loading) const LinearProgressIndicator(),
          if (_notice != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                _notice!,
                style: const TextStyle(color: AppColors.muted),
              ),
            ),
          const SizedBox(height: 12),
          const Text(
            'Với AI qua gateway, văn bản phụ đề gốc được gửi tới dịch vụ '
            'đã cấu hình trên PC; dịch vụ đó có thể chuyển văn bản lên Internet. '
            'Video và âm thanh không được gửi cho LLM. Bản sửa có thể đổi ý câu nói.',
            style: TextStyle(color: AppColors.muted, fontSize: 13, height: 1.6),
          ),
        ],
      ),
    ),
  );

  Widget _option(ReadingMethod method) {
    final available = !method.usesAi || _configured?[method.id] == true;
    final selected = widget.settings.readingMethod == method;
    return Card(
      color: selected ? AppColors.primarySoft : Colors.white,
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        enabled: available && !_saving,
        title: Text(
          method.label,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            '${method.description}${available || _loading ? '' : '\nCần cấu hình AI trên máy tính.'}',
            style: const TextStyle(height: 1.5),
          ),
        ),
        trailing: Icon(
          selected
              ? Icons.check_circle_rounded
              : available
              ? Icons.circle_outlined
              : Icons.lock_outline_rounded,
          color: selected ? AppColors.primary : AppColors.muted,
        ),
        onTap: available && !_saving ? () => _select(method) : null,
      ),
    );
  }
}
