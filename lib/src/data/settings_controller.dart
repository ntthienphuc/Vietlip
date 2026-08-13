import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsController extends ChangeNotifier {
  static const _apiUrlKey = 'lip_reader_api_url';
  static const _defaultApiUrl = 'http://10.0.2.2:7100';

  String _apiUrl = _defaultApiUrl;
  String get apiUrl => _apiUrl;

  Future<void> load() async {
    final preferences = await SharedPreferences.getInstance();
    _apiUrl = preferences.getString(_apiUrlKey) ?? _defaultApiUrl;
    notifyListeners();
  }

  Future<void> setApiUrl(String value) async {
    var normalized = value.trim();
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw const FormatException(
        'URL phải bắt đầu bằng http:// hoặc https://',
      );
    }
    _apiUrl = normalized;
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_apiUrlKey, normalized);
    notifyListeners();
  }
}
