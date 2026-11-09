import 'package:flutter/material.dart';

import '../../data/app_info.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';
import '../../widgets/app_brand.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({required this.settings, super.key});

  final SettingsController settings;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final Future<String?> _appVersion = AppInfo.version();
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
      _urlController.text = widget.settings.apiUrl;
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
              'Kết nối máy chủ',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _urlController,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'IP máy tính',
                hintText: '192.168.1.20:7100',
                prefixIcon: Icon(Icons.dns_outlined),
                helperText:
                    'Nhập IP hiển thị trên VietLip Server. Cổng mặc định: 7100.',
                helperMaxLines: 2,
              ),
            ),
            const SizedBox(height: 12),
            const ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.wifi_rounded, color: AppColors.primary),
              title: Text(
                'Cùng mạng Wi-Fi / LAN',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              subtitle: Text(
                'Mở VietLip Server trên máy tính và chờ “Sẵn sàng đọc môi”.',
              ),
            ),
            const SizedBox(height: 8),
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
                    Row(
                      children: [
                        Icon(
                          _health!['realtime_available'] == true
                              ? Icons.check_circle
                              : Icons.hourglass_top,
                          color: AppColors.primary,
                        ),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _health!['realtime_available'] == true
                                ? 'Sẵn sàng đọc môi'
                                : 'Máy chủ chưa sẵn sàng live',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _health!['realtime_available'] == true
                          ? 'Trở về Đọc môi và bấm Bắt đầu live.'
                          : 'Máy chủ đã phản hồi. Hãy chờ mô hình sẵn sàng rồi kiểm tra lại.',
                    ),
                    ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: const Text(
                        'Chi tiết kỹ thuật',
                        style: TextStyle(fontSize: 13),
                      ),
                      children: [
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            'Mô hình: ${_health!['model_state'] ?? 'chưa rõ'} · '
                            '${_health!['model_id'] ?? ''}\n'
                            'Thiết bị: ${_health!['device'] ?? 'chưa rõ'} · '
                            '${_health!['precision'] ?? ''}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.muted,
                            ),
                          ),
                        ),
                      ],
                    ),
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
              'Khi sử dụng',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Column(
                  children: [
                    _ArchitectureRow(
                      number: '1',
                      title: 'Giữ rõ khuôn mặt',
                      detail:
                          'Cầm máy dọc, nhìn gần chính diện và chọn nơi đủ sáng.',
                    ),
                    _ArchitectureRow(
                      number: '2',
                      title: 'Nói từng câu tự nhiên',
                      detail:
                          'Ứng dụng tự theo dõi môi và chốt đoạn khi bạn ngừng nói.',
                    ),
                    _ArchitectureRow(
                      number: '3',
                      title: 'Đọc và kiểm tra phụ đề',
                      detail:
                          'Chữ gạch dưới còn có thể đổi. Phụ đề tự động có thể nhận sai.',
                      last: true,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 22),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const BrandMark(),
              title: FutureBuilder<String?>(
                future: _appVersion,
                builder: (context, snapshot) => Text(
                  snapshot.data?.isNotEmpty == true
                      ? '${AppBrand.name} ${snapshot.data}'
                      : AppBrand.name,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              subtitle: const Text('Đọc môi tiếng Việt · bản thử nghiệm'),
            ),
            const SizedBox(height: 12),
            const Card(
              child: ListTile(
                leading: Icon(Icons.privacy_tip_outlined),
                title: Text(
                  'Quyền riêng tư',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  'Video lưu trên điện thoại có âm thanh để đối chiếu. Phụ đề live chỉ gửi hình ảnh tới máy chủ. '
                  'Lịch sử lưu trên thiết bị; ứng dụng không tự dùng video để huấn luyện. ',
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
