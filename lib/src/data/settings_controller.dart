import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsController extends ChangeNotifier {
  static const _apiUrlKey = 'lip_reader_api_url';
  static const _defaultApiUrl = '';

  String _apiUrl = _defaultApiUrl;
  String get apiUrl => _apiUrl;

  Future<void> load() async {
    final preferences = await SharedPreferences.getInstance();
    _apiUrl = preferences.getString(_apiUrlKey) ?? _defaultApiUrl;
    // Old internal builds used USB forwarding or the Android emulator.
    // Ask for the PC's LAN address when upgrading those installations.
    if ({
      '127.0.0.1',
      'localhost',
      '10.0.2.2',
    }.contains(Uri.tryParse(_apiUrl)?.host)) {
      _apiUrl = '';
    }
    notifyListeners();
  }

  Future<void> setApiUrl(String value) async {
    final normalized = normalizeServerAddress(value);
    _apiUrl = normalized;
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_apiUrlKey, normalized);
    notifyListeners();
  }

  static String normalizeServerAddress(String value) {
    var normalized = value.trim();
    if (normalized.isEmpty) {
      throw const FormatException('Nhập IP đang hiển thị trên VietLip Server.');
    }
    if (!normalized.contains('://')) normalized = 'http://$normalized';
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null ||
        !{'http', 'https'}.contains(uri.scheme) ||
        uri.host.isEmpty) {
      throw const FormatException('Nhập IP hoặc địa chỉ http:// của máy chủ.');
    }
    if (uri.userInfo.isNotEmpty ||
        uri.path.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        uri.host.contains(RegExp(r'\s')) ||
        uri.port == 0 ||
        uri.port > 65535) {
      throw const FormatException(
        'Chỉ nhập IP và cổng, ví dụ 192.168.1.20:7100.',
      );
    }
    return uri.scheme == 'http' && !uri.hasPort
        ? uri.replace(port: 7100).toString()
        : uri.toString();
  }
}
