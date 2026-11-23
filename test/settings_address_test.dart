import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/settings_controller.dart';
import 'package:lip_reader/src/models/reading_method.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('existing suggestion sessions use Gemini after upgrading', () async {
    SharedPreferences.setMockInitialValues({
      'vietlip_ai_provider_v1': 'groq',
      'vietlip_reading_method_v1': 'gateway_direct',
      'lip_reader_api_url': 'http://192.168.1.20:7100',
    });
    final settings = SettingsController();
    await settings.load();
    expect(settings.aiProvider, AiProvider.gemini);
    expect(settings.readingMethod, ReadingMethod.recovery);
    expect(settings.apiUrl, 'http://192.168.1.20:7100');
  });
  test('LAN address entry accepts IP, explicit port and full URL', () {
    expect(
      SettingsController.normalizeServerAddress(' 192.168.1.20 '),
      'http://192.168.1.20:7100',
    );
    expect(
      SettingsController.normalizeServerAddress('172.16.0.9:7102'),
      'http://172.16.0.9:7102',
    );
    expect(
      SettingsController.normalizeServerAddress('http://192.168.1.20:7100/'),
      'http://192.168.1.20:7100',
    );
    for (final invalid in [
      '',
      'ftp://192.168.1.20',
      'http://host/path',
      'http://user:pass@host',
      'http://host:70000',
    ]) {
      expect(
        () => SettingsController.normalizeServerAddress(invalid),
        throwsFormatException,
      );
    }
  });
  test(
    'upgrade clears obsolete USB address without deleting other app data',
    () async {
      SharedPreferences.setMockInitialValues({
        'lip_reader_api_url': 'http://127.0.0.1:7100',
        'history': 'retained',
      });
      final settings = SettingsController();
      await settings.load();
      expect(settings.apiUrl, isEmpty);
      await settings.setApiUrl('172.16.0.9');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('history'), 'retained');
      expect(prefs.getString('lip_reader_api_url'), 'http://172.16.0.9:7100');
    },
  );
}
