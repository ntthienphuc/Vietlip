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
          'Khôi phục câu hiện bản gốc ở trên, kết quả AI ở dưới ngay trong phiên live.',
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
  late AiProvider _provider = widget.settings.aiProvider;

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
      setState(() {
        _configuration = result;
        if (_providerInfo(_provider)?['configured'] != true) {
          for (final candidate in AiProvider.values) {
            if (_providerInfo(candidate)?['configured'] == true) {
              _provider = candidate;
              break;
            }
          }
        }
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => _notice = 'Kết nối VietLip Server để kiểm tra dịch vụ AI.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.settings.setAiProvider(_provider);
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
                    const Text(
                      'Dịch vụ khôi phục',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    for (final provider in AiProvider.values)
                      Builder(
                        builder: (context) {
                          final info = _providerInfo(provider);
                          final available = info?['configured'] == true;
                          return ListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 4,
                            ),
                            enabled: available && !_saving,
                            title: Text(provider.label),
                            subtitle: Text(
                              available
                                  ? (info?['model_id']?.toString() ??
                                        provider.subtitle)
                                  : _loading
                                  ? 'Đang kiểm tra…'
                                  : 'Chưa cấu hình trên PC',
                            ),
                            trailing: Icon(
                              _provider == provider && available
                                  ? Icons.radio_button_checked
                                  : Icons.radio_button_off,
                              color: available
                                  ? AppColors.primary
                                  : AppColors.muted,
                            ),
                            onTap: available && !_saving
                                ? () => setState(() => _provider = provider)
                                : null,
                          );
                        },
                      ),
                    const SizedBox(height: 8),
                    const Text(
                      'Mỗi câu đã chốt được gửi một lần. Chỉ văn bản đi tới dịch vụ AI. Bản khôi phục có thể sai ý.',
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
