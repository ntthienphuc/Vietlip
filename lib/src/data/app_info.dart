import 'package:flutter/services.dart';

/// Read the installed package version so the settings label cannot go stale.
abstract final class AppInfo {
  static const _channel = MethodChannel('vn.lipread/app_info');

  static Future<String?> version() async {
    try {
      return await _channel.invokeMethod<String>('getVersion');
    } on MissingPluginException {
      return null;
    } on PlatformException {
      return null;
    }
  }
}
