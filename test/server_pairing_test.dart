import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/features/settings/server_pairing.dart';

String code(String address) => Uri(
  scheme: 'vietlip',
  host: 'pair',
  queryParameters: {'server': address},
).toString();

void main() {
  test('reads the Windows pairing URI with its exact LAN address and port', () {
    expect(
      readPairingAddress(
        'vietlip://pair?server=http%3A%2F%2F192.168.1.8%3A7100',
      ),
      'http://192.168.1.8:7100',
    );
    expect(
      readPairingAddress(code('http://172.16.1.2:7250')),
      'http://172.16.1.2:7250',
    );
  });

  test('rejects other QR formats and invalid pairing addresses', () {
    for (final value in [
      'https://example.org',
      code('http://example.org:7100'),
      code('http://127.0.0.1:7100'),
      code('http://192.168.1.8'),
      code('http://192.168.1.8:7100/reset'),
      code('http://192.168.1.8:7100?foo=bar'),
      code('http://admin@192.168.1.8:7100'),
      '${code('http://192.168.1.8:7100')}&server=unexpected',
    ]) {
      expect(
        () => readPairingAddress(value),
        throwsFormatException,
        reason: value,
      );
    }
  });
}
