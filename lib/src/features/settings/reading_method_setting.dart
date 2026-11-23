import 'package:flutter/material.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../models/reading_method.dart';
import '../../theme/app_theme.dart';

class ReadingMethodSetting extends StatelessWidget {
  const ReadingMethodSetting({required this.settings, super.key});
  final SettingsController settings;

  static Future<void> showPicker(
    BuildContext context,
    SettingsController settings,
  ) => showModalBottomSheet<void>(
    context: context,
    useRootNavigator: true,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => _MethodPicker(settings: settings),
  );

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: settings,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Cách đọc môi',
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
                  ? Icons.auto_awesome_rounded
                  : Icons.closed_caption_outlined,
              color: AppColors.primary,
            ),
            title: Text(
              settings.readingMethod.label,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              settings.readingMethod.usesAi
                  ? '${settings.aiProvider.label} · tự động theo từng câu'
                  : 'Hiện trực tiếp kết quả đọc khẩu hình',
              style: const TextStyle(color: AppColors.muted, height: 1.6),
            ),
            trailing: const Icon(Icons.tune_rounded),
            onTap: () => showPicker(context, settings),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Bật Kèm gợi ý câu để xem thêm một cách diễn đạt khi bạn ngừng nói.',
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
  Map<String, dynamic>? _configuration;
  bool _loading = true, _saving = false;
  String? _notice;
  late ReadingMethod _method = widget.settings.readingMethod;
  static const _provider = AiProvider.gemini;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Map? _providerInfo(AiProvider provider) {
    for (final row in _configuration?['providers'] as List? ?? const []) {
      if (row is Map && row['id'] == provider.id) return row;
    }
    return null;
  }

  Future<void> _check() async {
    setState(() {
      _loading = true;
      _notice = null;
    });
    try {
      final result = await LipReaderApi(widget.settings).rewriteConfiguration();
      if (!mounted) return;
      setState(() => _configuration = result);
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              _notice = 'Kết nối VietLip Server để kiểm tra dịch vụ gợi ý câu.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.settings.setReadingMethod(_method);
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        setState(() {
          _saving = false;
          _notice = 'Chưa lưu được lựa chọn. Hãy thử lại.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        0,
        20,
        20 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * .82,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Cách đọc môi',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            const Text(
              'Lựa chọn áp dụng khi bắt đầu phiên mới.',
              style: TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 18),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final method in ReadingMethod.values) ...[
                    Card(
                      color: _method == method
                          ? AppColors.primarySoft
                          : Colors.white,
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(16),
                        leading: Icon(
                          method.usesAi
                              ? Icons.auto_awesome_rounded
                              : Icons.closed_caption_outlined,
                          color: AppColors.primary,
                        ),
                        title: Text(
                          method.label,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            method.description,
                            style: const TextStyle(height: 1.5),
                          ),
                        ),
                        trailing: Icon(
                          _method == method
                              ? Icons.check_circle_rounded
                              : Icons.circle_outlined,
                          color: AppColors.primary,
                        ),
                        onTap: _saving
                            ? null
                            : () => setState(() => _method = method),
                      ),
                    ),
                    const SizedBox(height: 10),
                  ],
                  if (_method.usesAi) ...[
                    const SizedBox(height: 10),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.auto_awesome_outlined),
                      title: const Text('Gemini'),
                      subtitle: Text(
                        _loading
                            ? 'Đang kiểm tra máy chủ…'
                            : _providerInfo(_provider)?['configured'] == true
                            ? 'Đã cấu hình trên máy tính'
                            : 'Mở VietLip Server trên PC và chọn Cài đặt key Gemini.',
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'PC gửi phần chữ của từng câu đã chốt đến Gemini. Mô hình ngôn ngữ lớn (LLM) gợi ý cách diễn đạt tự nhiên hơn. Gợi ý có thể khác ý bạn.',
                      style: TextStyle(
                        color: AppColors.muted,
                        fontSize: 12,
                        height: 1.5,
                      ),
                    ),
                  ],
                  if (_loading)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: LinearProgressIndicator(),
                    ),
                  if (_notice != null)
                    Text(
                      _notice!,
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  if (!_loading &&
                      _method.usesAi &&
                      _providerInfo(_provider)?['configured'] != true)
                    TextButton.icon(
                      onPressed: _check,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Kiểm tra lại máy chủ'),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed:
                  _saving ||
                      (_method.usesAi &&
                          _providerInfo(_provider)?['configured'] != true)
                  ? null
                  : _save,
              child: Text(_saving ? 'Đang lưu…' : 'Áp dụng'),
            ),
          ],
        ),
      ),
    ),
  );
}
