import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../data/lip_reader_api.dart';
import '../../theme/app_theme.dart';
import '../../widgets/status_notice.dart';
import 'server_pairing.dart';

typedef ServerQrMatch = ({String address, Map<String, dynamic> health});

enum _ScanPhase { scanning, checking, connected, failed }

class ServerQrScanner extends StatefulWidget {
  const ServerQrScanner({super.key, this.checkServer = checkPairingServer});

  final Future<Map<String, dynamic>> Function(String) checkServer;

  @override
  State<ServerQrScanner> createState() => _ServerQrScannerState();
}

class _ServerQrScannerState extends State<ServerQrScanner> {
  final _scanner = MobileScannerController(
    facing: CameraFacing.back,
    formats: const [BarcodeFormat.qrCode],
  );
  _ScanPhase _phase = _ScanPhase.scanning;
  bool _invalidCode = false;
  String? _connectionError;

  @override
  void dispose() {
    _scanner.dispose();
    super.dispose();
  }

  Future<void> _detect(BarcodeCapture capture) async {
    if (!mounted || _phase != _ScanPhase.scanning) return;
    for (final barcode in capture.barcodes) {
      final raw = barcode.rawValue;
      if (raw == null) continue;
      String address;
      try {
        address = readPairingAddress(raw);
      } on FormatException {
        continue;
      }
      await _connect(address);
      return;
    }
    if (!_invalidCode) setState(() => _invalidCode = true);
  }

  Future<void> _connect(String address) async {
    setState(() => _phase = _ScanPhase.checking);
    // Keep the first feedback on-screen even when the LAN responds instantly.
    final feedback = Future<void>.delayed(const Duration(milliseconds: 450));
    Map<String, dynamic> health;
    try {
      health = await widget.checkServer(address);
      await feedback;
    } catch (error) {
      await feedback;
      if (mounted) {
        setState(() {
          _connectionError = LipReaderApi.readableError(error);
          _phase = _ScanPhase.failed;
        });
      }
      return;
    }
    if (!mounted || ModalRoute.of(context)?.isCurrent != true) return;
    setState(() => _phase = _ScanPhase.connected);
    await Future<void>.delayed(const Duration(milliseconds: 1200));
    if (!mounted || ModalRoute.of(context)?.isCurrent != true) return;
    try {
      await _scanner.stop();
    } on MobileScannerException {
      // Leaving this screen also disposes the camera.
    }
    if (mounted && ModalRoute.of(context)?.isCurrent == true) {
      Navigator.of(
        context,
      ).pop<ServerQrMatch>((address: address, health: health));
    }
  }

  Widget _scanStatus() => switch (_phase) {
    _ScanPhase.scanning => Text(
      _invalidCode
          ? 'Đây chưa phải mã kết nối VietLip. Hãy đưa đúng mã trên PC vào khung.'
          : 'Hướng camera vào mã QR lớn trong cửa sổ VietLip Server.',
      textAlign: TextAlign.center,
      style: const TextStyle(color: AppColors.ink, height: 1.4),
    ),
    _ScanPhase.checking => const StatusNotice(
      title: 'Đã nhận mã QR',
      detail: 'Đang kết nối với VietLip Server…',
      busy: true,
    ),
    _ScanPhase.connected => const StatusNotice(
      title: 'Đã kết nối với máy chủ',
      detail: 'Đang quay về Cài đặt…',
    ),
    _ScanPhase.failed => StatusNotice(
      title: 'Chưa kết nối được máy chủ',
      detail: _connectionError,
      error: true,
      action: 'Quét lại',
      onAction: () => setState(() {
        _phase = _ScanPhase.scanning;
        _invalidCode = false;
      }),
    ),
  };

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Quét QR máy chủ')),
    body: SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: LayoutBuilder(
              builder: (context, size) {
                final side = (size.biggest.shortestSide * .74).clamp(
                  0.0,
                  360.0,
                );
                final window = Rect.fromCenter(
                  center: size.biggest.center(Offset.zero),
                  width: side,
                  height: side,
                );
                return Stack(
                  fit: StackFit.expand,
                  children: [
                    MobileScanner(
                      controller: _scanner,
                      scanWindow: window,
                      onDetect: _detect,
                      placeholderBuilder: (_) =>
                          const Center(child: CircularProgressIndicator()),
                      errorBuilder: (_, error) => ColoredBox(
                        color: AppColors.canvas,
                        child: Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(
                              error.errorCode ==
                                      MobileScannerErrorCode.permissionDenied
                                  ? 'Cho phép VietLip dùng camera trong Cài đặt điện thoại, hoặc quay lại nhập IP.'
                                  : 'Chưa mở được camera. Quay lại để thử lại hoặc nhập IP.',
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (_scanner.value.error == null)
                      Positioned.fromRect(
                        rect: window,
                        child: IgnorePointer(
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: _phase == _ScanPhase.connected
                                    ? AppColors.primary
                                    : Colors.white,
                                width: 3,
                              ),
                              borderRadius: BorderRadius.circular(20),
                            ),
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
          Padding(padding: const EdgeInsets.all(20), child: _scanStatus()),
        ],
      ),
    ),
  );
}
