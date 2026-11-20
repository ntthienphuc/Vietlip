import 'package:dio/dio.dart';

import '../../data/lip_reader_api.dart';
import '../../data/settings_controller.dart';

/// A QR can select a VietLip address on the LAN. It never opens a web page.
String readPairingAddress(String value) {
  const invalid = FormatException(
    'Hãy quét mã QR trong cửa sổ VietLip Server.',
  );
  if (value.length > 256) throw invalid;
  final link = Uri.tryParse(value);
  if (link == null ||
      !link.isScheme('vietlip') ||
      link.authority != 'pair' ||
      link.path.isNotEmpty ||
      link.hasFragment) {
    throw invalid;
  }
  final parameters = link.queryParametersAll;
  final servers = parameters['server'];
  if (parameters.length != 1 || servers == null || servers.length != 1) {
    throw invalid;
  }
  final url = Uri.tryParse(servers.single);
  if (url == null || !url.isScheme('http') || !url.hasPort) throw invalid;
  final address = SettingsController.normalizeServerAddress(servers.single);
  final octets = url.host.split('.');
  final numbers = octets.map(int.tryParse).toList();
  if (numbers.length != 4 ||
      numbers.asMap().entries.any(
        (item) =>
            item.value == null ||
            item.value! < 0 ||
            item.value! > 255 ||
            item.value.toString() != octets[item.key],
      )) {
    throw invalid;
  }
  final lan =
      numbers[0] == 10 ||
      (numbers[0] == 172 && numbers[1]! >= 16 && numbers[1]! <= 31) ||
      (numbers[0] == 192 && numbers[1] == 168);
  if (!lan) throw invalid;
  return address;
}

Future<Map<String, dynamic>> checkPairingServer(String address) async {
  final client = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 4),
      followRedirects: false,
    ),
  );
  try {
    final health = await LipReaderApi.atAddress(address, dio: client).health();
    if (health['service'] != 'lip-reader-api' ||
        !{'ok', 'degraded'}.contains(health['status'])) {
      throw const FormatException(
        'Địa chỉ trong mã QR không phải VietLip Server.',
      );
    }
    return health;
  } finally {
    client.close(force: true);
  }
}
