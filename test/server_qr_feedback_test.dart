import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/features/settings/server_qr_scanner.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class _Camera extends MobileScannerPlatform {
  final detections = StreamController<BarcodeCapture?>.broadcast();

  @override
  Stream<BarcodeCapture?> get barcodesStream => detections.stream;
  @override
  Stream<TorchState> get torchStateStream => const Stream.empty();
  @override
  Stream<double> get zoomScaleStateStream => const Stream.empty();
  @override
  Widget buildCameraView() => const ColoredBox(color: Colors.black);

  @override
  Future<MobileScannerViewAttributes> start(StartOptions options) async =>
      const MobileScannerViewAttributes(
        cameraDirection: CameraFacing.back,
        currentTorchMode: TorchState.off,
        size: Size(640, 480),
      );

  @override
  Future<void> stop() async {}
  @override
  Future<void> updateScanWindow(Rect? window) async {}
  @override
  Future<void> dispose() async {}
}

const _code = BarcodeCapture(
  barcodes: [
    Barcode(
      format: BarcodeFormat.qrCode,
      rawValue: 'vietlip://pair?server=http%3A%2F%2F192.168.1.8%3A7100',
    ),
  ],
);
const _address = 'http://192.168.1.8:7100';

void main() {
  late _Camera camera;
  late MobileScannerPlatform previous;

  setUp(() {
    previous = MobileScannerPlatform.instance;
    camera = _Camera();
    MobileScannerPlatform.instance = camera;
  });
  tearDown(() async {
    MobileScannerPlatform.instance = previous;
    await camera.detections.close();
  });

  testWidgets('a QR already in view shows feedback before it returns', (
    tester,
  ) async {
    ServerQrMatch? result;
    var checks = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () async {
                result = await Navigator.of(context).push<ServerQrMatch>(
                  MaterialPageRoute(
                    builder: (_) => ServerQrScanner(
                      checkServer: (address) async {
                        expect(address, _address);
                        checks++;
                        return {'realtime_available': true};
                      },
                    ),
                  ),
                );
              },
              child: const Text('Quét'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Quét'));
    await tester.pumpAndSettle();
    camera.detections.add(_code);
    camera.detections.add(_code);
    await tester.pump();
    await tester.pump();
    expect(find.text('Đã nhận mã QR'), findsOneWidget);
    expect(find.byType(MobileScanner), findsOneWidget);
    expect(checks, 1);
    expect(result, isNull);

    await tester.pump(const Duration(milliseconds: 450));
    await tester.pump();
    expect(find.text('Đã kết nối với máy chủ'), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
    expect(result, isNull);
    expect(find.byType(MobileScanner), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pumpAndSettle();
    expect(result?.address, _address);
    expect(result?.health['realtime_available'], isTrue);
  });

  testWidgets('connection failure stays on the scanner with a retry', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ServerQrScanner(
          checkServer: (_) async =>
              throw const FormatException('Máy chủ thử nghiệm không phản hồi.'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    camera.detections.add(_code);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 450));
    expect(find.text('Máy chủ thử nghiệm không phản hồi.'), findsOneWidget);
    expect(find.byType(MobileScanner), findsOneWidget);
    await tester.tap(find.text('Quét lại'));
    await tester.pump();
    expect(find.textContaining('Hướng camera'), findsOneWidget);
  });
}
