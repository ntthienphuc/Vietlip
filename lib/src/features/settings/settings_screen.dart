import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/app_info.dart';
import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';
import '../../widgets/app_brand.dart';
import '../../widgets/status_notice.dart';
import '../../widgets/connection_diagram.dart';
import 'reading_method_setting.dart';
import 'server_qr_scanner.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({required this.settings, super.key});
  final SettingsController settings;
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final Future<String?> _appVersion = AppInfo.version();
  late final _urlController = TextEditingController(
    text: widget.settings.apiUrl,
  );
  Map<String, dynamic>? _health;
  String? _error, _fieldError;
  bool _checking = false, _scanning = false;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _saveAndCheck() async {
    if (_checking) return;
    FocusScope.of(context).unfocus();
    String address;
    try {
      address = SettingsController.normalizeServerAddress(_urlController.text);
    } on FormatException catch (error) {
      setState(() {
        _fieldError = error.message;
        _health = null;
        _error = null;
      });
      return;
    }
    await _checkAddress(address);
  }

  Future<void> _scanQr() async {
    if (_checking || _scanning) return;
    FocusScope.of(context).unfocus();
    _scanning = true;
    try {
      final match = await Navigator.of(context, rootNavigator: true)
          .push<ServerQrMatch>(
            MaterialPageRoute(builder: (_) => const ServerQrScanner()),
          );
      if (!mounted || match == null) return;
      await widget.settings.setApiUrl(match.address);
      if (mounted) {
        _urlController.text = widget.settings.apiUrl;
        setState(() {
          _health = match.health;
          _error = _fieldError = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = LipReaderApi.readableError(error));
    } finally {
      _scanning = false;
    }
  }

  Future<void> _checkAddress(String address) async {
    setState(() {
      _checking = true;
      _error = _fieldError = null;
      _health = null;
    });
    try {
      await widget.settings.setApiUrl(address);
      if (!mounted) return;
      _urlController.text = widget.settings.apiUrl;
      final health = await LipReaderApi.atAddress(address).health();
      if (mounted) setState(() => _health = health);
    } catch (error) {
      if (mounted) setState(() => _error = LipReaderApi.readableError(error));
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final supportsScanner =
        !kIsWeb &&
        {
          TargetPlatform.android,
          TargetPlatform.iOS,
        }.contains(defaultTargetPlatform);
    final ready = _health?['realtime_available'] == true;
    final failed =
        _health?['status'] == 'degraded' || _health?['last_error'] != null;
    return SafeArea(
      child: Scaffold(
        appBar: AppBar(title: const Text('Cài đặt')),
        body: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
              children: [
                const ConnectionDiagram(),
                const SizedBox(height: 26),
                const Text(
                  'Kết nối máy tính',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Mở VietLip Server trên máy tính. Điện thoại và máy tính cần dùng chung mạng Wi-Fi.',
                  style: TextStyle(color: AppColors.muted, height: 1.6),
                ),
                const SizedBox(height: 24),
                if (supportsScanner) ...[
                  FilledButton.icon(
                    onPressed: _checking ? null : _scanQr,
                    icon: const Icon(Icons.qr_code_scanner_rounded),
                    label: const Text('Quét QR máy chủ'),
                  ),
                  const SizedBox(height: 16),
                ],
                if (_checking) ...[
                  const LinearProgressIndicator(),
                  const SizedBox(height: 8),
                  const Text(
                    'Đang kiểm tra máy chủ trong mạng nội bộ…',
                    style: TextStyle(color: AppColors.muted),
                  ),
                ],
                if (_health != null) ...[
                  const SizedBox(height: 12),
                  StatusNotice(
                    title: ready
                        ? 'Sẵn sàng đọc môi'
                        : failed
                        ? 'Máy chủ chưa thể đọc môi'
                        : 'Đã kết nối, máy chủ đang chuẩn bị',
                    detail: ready
                        ? 'Đã lưu địa chỉ máy chủ trên điện thoại.'
                        : failed
                        ? 'Mở cửa sổ VietLip Server để xem lỗi khởi động, rồi kiểm tra lại.'
                        : 'Đã lưu địa chỉ. Chờ VietLip Server báo sẵn sàng.',
                    busy: !ready && !failed,
                    error: failed,
                    action: ready ? 'Về màn hình đọc môi' : null,
                    onAction: ready ? () => context.go('/read') : null,
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  StatusNotice(
                    title: 'Chưa kết nối được máy chủ',
                    detail: _error,
                    error: true,
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: _urlController,
                  enabled: !_checking,
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                  enableSuggestions: false,
                  onSubmitted: (_) => _saveAndCheck(),
                  onChanged: (_) => setState(() {
                    _health = null;
                    _error = _fieldError = null;
                  }),
                  decoration: InputDecoration(
                    labelText: 'Địa chỉ máy chủ',
                    hintText: '192.168.1.20:7100',
                    prefixIcon: const Icon(Icons.computer_outlined),
                    helperText: 'Nhập IP hiển thị trong cửa sổ VietLip Server.',
                    helperMaxLines: 2,
                    errorText: _fieldError,
                    errorMaxLines: 3,
                  ),
                ),
                const SizedBox(height: 20),
                OutlinedButton.icon(
                  onPressed: _checking ? null : _saveAndCheck,
                  icon: _checking
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.wifi_rounded),
                  label: Text(_checking ? 'Đang kiểm tra…' : 'Lưu và kiểm tra'),
                ),
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 20),
                ReadingMethodSetting(settings: widget.settings),
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 8),
                const ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: EdgeInsets.only(bottom: 16),
                  leading: Icon(Icons.face_outlined),
                  title: Text('Để đọc môi rõ hơn'),
                  children: [
                    _HelpLine(
                      icon: Icons.wb_sunny_outlined,
                      text: 'Chọn nơi đủ sáng, để nguồn sáng phía trước mặt.',
                    ),
                    _HelpLine(
                      icon: Icons.center_focus_strong_outlined,
                      text:
                          'Giữ máy dọc, thấy rõ miệng và hạn chế quay nghiêng.',
                    ),
                    _HelpLine(
                      icon: Icons.short_text_rounded,
                      text:
                          'Nói từng câu tự nhiên. Ứng dụng tự chốt câu khi bạn ngừng nói.',
                    ),
                    _HelpLine(
                      icon: Icons.closed_caption_outlined,
                      text:
                          'Chữ gạch dưới còn có thể đổi. Hãy kiểm tra lại phụ đề.',
                    ),
                  ],
                ),
                const ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: EdgeInsets.fromLTRB(0, 0, 0, 16),
                  leading: Icon(Icons.privacy_tip_outlined),
                  title: Text('Video và quyền riêng tư'),
                  children: [
                    Text(
                      'Phụ đề trực tiếp chỉ dùng hình ảnh gửi tới máy chủ bạn đã chọn. '
                      'Nếu bật Kèm gợi ý câu, từng câu đã chốt được gửi tới Google Gemini qua PC. '
                      'Video có âm thanh được lưu trên điện thoại để đối chiếu. '
                      'Lịch sử lưu trên thiết bị; ứng dụng không tự dùng video để huấn luyện.',
                      style: TextStyle(color: AppColors.muted, height: 1.6),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    const BrandMark(size: 36),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          FutureBuilder<String?>(
                            future: _appVersion,
                            builder: (context, snapshot) => Text(
                              snapshot.data?.isNotEmpty == true
                                  ? '${AppBrand.name} ${snapshot.data}'
                                  : AppBrand.name,
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const Text(
                            'Đọc môi tiếng Việt · bản thử nghiệm',
                            style: TextStyle(
                              fontSize: 13,
                              color: AppColors.muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HelpLine extends StatelessWidget {
  const _HelpLine({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.primary, size: 22),
        const SizedBox(width: 12),
        Expanded(child: Text(text, style: const TextStyle(height: 1.5))),
      ],
    ),
  );
}
