import 'package:flutter/material.dart';

import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';
import '../../theme/app_theme.dart';

/// Readiness is checked against the saved address; a saved IP is not success.
class ServerConnectionBanner extends StatefulWidget {
  const ServerConnectionBanner({
    super.key,
    required this.settings,
    required this.active,
    required this.onConfigure,
    this.loadHealth,
  });
  final SettingsController settings;
  final bool active;
  final VoidCallback onConfigure;
  final Future<Map<String, dynamic>> Function()? loadHealth;

  @override
  State<ServerConnectionBanner> createState() => _ServerConnectionBannerState();
}

class _ServerConnectionBannerState extends State<ServerConnectionBanner> {
  bool _checking = false, _ready = false, _reachable = false, _failed = false;
  int _request = 0;

  @override
  void initState() {
    super.initState();
    widget.settings.addListener(_check);
    _check();
  }

  @override
  void didUpdateWidget(ServerConnectionBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.settings != widget.settings) {
      oldWidget.settings.removeListener(_check);
      widget.settings.addListener(_check);
      _check();
    } else if (widget.active && !oldWidget.active) {
      _check();
    }
  }

  @override
  void dispose() {
    _request++;
    widget.settings.removeListener(_check);
    super.dispose();
  }

  Future<void> _check() async {
    final request = ++_request;
    setState(() {
      _ready = _reachable = _failed = false;
      _checking = widget.active && widget.settings.apiUrl.isNotEmpty;
    });
    if (!_checking) return;
    try {
      final health =
          await (widget.loadHealth?.call() ??
              LipReaderApi(widget.settings).health());
      if (!mounted || request != _request) return;
      setState(() {
        _reachable = true;
        _failed =
            health['status'] == 'degraded' || health['last_error'] != null;
        _ready = health['realtime_available'] == true;
      });
    } catch (_) {
      // The actionable connection diagnosis is available in Settings.
    } finally {
      if (mounted && request == _request) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final configured = widget.settings.apiUrl.isNotEmpty;
    final title = _checking
        ? 'Đang kiểm tra máy chủ…'
        : _ready
        ? 'Máy chủ sẵn sàng'
        : _failed
        ? 'Máy chủ cần kiểm tra'
        : _reachable
        ? 'Máy chủ đang chuẩn bị'
        : configured
        ? 'Chưa kết nối được máy chủ'
        : 'Kết nối máy tính để bắt đầu';
    final detail = configured
        ? Uri.tryParse(widget.settings.apiUrl)?.authority ??
              widget.settings.apiUrl
        : 'Mở VietLip Server, rồi nhập IP trong Cài đặt';
    return Material(
      color: _ready ? AppColors.primarySoft : Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: widget.onConfigure,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 12),
          child: Row(
            children: [
              Icon(
                _ready ? Icons.wifi_rounded : Icons.computer_outlined,
                color: _ready ? AppColors.primary : AppColors.muted,
                size: 19,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      detail,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              if (_checking)
                const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                const Icon(Icons.chevron_right_rounded, color: AppColors.muted),
            ],
          ),
        ),
      ),
    );
  }
}
