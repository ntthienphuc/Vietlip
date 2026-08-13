import 'package:flutter/material.dart';

import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({required this.settings, super.key});

  final SettingsController settings;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _urlController = TextEditingController(
    text: widget.settings.apiUrl,
  );
  Map<String, dynamic>? _health;
  String? _error;
  bool _checking = false;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _saveAndCheck() async {
    setState(() {
      _checking = true;
      _error = null;
      _health = null;
    });
    try {
      await widget.settings.setApiUrl(_urlController.text);
      final health = await LipReaderApi(widget.settings).health();
      if (mounted) setState(() => _health = health);
    } catch (error) {
      if (mounted) setState(() => _error = LipReaderApi.readableError(error));
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Scaffold(
        appBar: AppBar(
          title: const Text(
            'Cài đặt',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            const Text(
              'Máy chủ suy luận',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _urlController,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'Địa chỉ máy chủ',
                hintText: 'http://192.168.1.20:7100',
                prefixIcon: Icon(Icons.dns_outlined),
                helperText:
                    'Nhập địa chỉ LAN được hiển thị trong Lip Reader Server.',
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _checking ? null : _saveAndCheck,
              icon: _checking
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.wifi_tethering_rounded),
              label: Text(_checking ? 'Đang kiểm tra…' : 'Lưu và kiểm tra'),
            ),
            if (_health != null) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(15),
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.check_circle, color: AppColors.primary),
                        SizedBox(width: 8),
                        Text(
                          'Đã kết nối máy chủ',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Mô hình: ${_health!['model_state'] ?? 'chưa rõ'} · '
                      'Thiết bị: ${_health!['device'] ?? 'chưa rõ'} '
                      '(${_health!['precision'] ?? 'chưa rõ'})\n'
                      'LLM: ${_health!['llm_available'] == true ? _health!['llm_model'] : 'chưa cấu hình'}',
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Phụ đề trực tiếp: ${_health!['realtime_available'] == true ? 'sẵn sàng' : 'chưa bật'}',
                    ),
                    if ((_health!['device'] ?? '').toString().startsWith(
                      'cpu',
                    )) ...[
                      const SizedBox(height: 8),
                      const Text(
                        'Máy chủ đang chạy CPU: vẫn suy luận đầy đủ, nhưng lượt '
                        'xử lý đầu tiên sẽ chậm hơn vì phải nạp mô hình.',
                        style: TextStyle(color: AppColors.muted),
                      ),
                    ],
                  ],
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 14),
              Text(_error!, style: const TextStyle(color: AppColors.error)),
            ],
            const SizedBox(height: 26),
            const Text(
              'Cách hệ thống hoạt động',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Column(
                  children: [
                    _ArchitectureRow(
                      number: '1',
                      title: 'Thu nhận video',
                      detail: 'Quay đoạn nói ngắn, không thu âm.',
                    ),
                    _ArchitectureRow(
                      number: '2',
                      title: 'Căn chỉnh miệng',
                      detail:
                          'Hệ thống tự căn chỉnh khuôn mặt và tạo vùng môi chuẩn hóa ở 25 fps.',
                    ),
                    _ArchitectureRow(
                      number: '3',
                      title: 'Auto-AVSR',
                      detail: 'Conformer đọc chuỗi chuyển động môi tiếng Việt.',
                    ),
                    _ArchitectureRow(
                      number: '4',
                      title: 'Xác nhận kết quả',
                      detail:
                          'Hiển thị câu và ứng viên để người dùng xác nhận.',
                      last: true,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 22),
            const Card(
              child: ListTile(
                leading: Icon(Icons.privacy_tip_outlined),
                title: Text(
                  'Quyền riêng tư',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  'Máy chủ xóa tệp tạm sau mỗi lượt xử lý. Lịch sử văn bản chỉ lưu '
                  'trên thiết bị; ứng dụng không tự tải dữ liệu lên để huấn luyện.',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ArchitectureRow extends StatelessWidget {
  const _ArchitectureRow({
    required this.number,
    required this.title,
    required this.detail,
    this.last = false,
  });

  final String number;
  final String title;
  final String detail;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 17,
            backgroundColor: AppColors.primarySoft,
            foregroundColor: AppColors.primary,
            child: Text(
              number,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                Text(detail, style: const TextStyle(color: AppColors.muted)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
