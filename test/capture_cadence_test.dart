import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/src/data/capture_cadence.dart';

void main() {
  test('30 fps camera retains 25 fps over ten seconds', () {
    final cadence = CaptureCadence();
    var accepted = 0;
    for (var i = 0; i < 300; i++) {
      if (cadence.accept((i * 1000000 / 30).round(), 25)) accepted++;
    }
    expect(accepted, inInclusiveRange(249, 251));
  });
  test('capture resumes after a stall without a burst', () {
    final cadence = CaptureCadence();
    expect(cadence.accept(0, 25), isTrue);
    expect(cadence.accept(1000000, 25), isTrue);
    expect(cadence.accept(1000001, 25), isFalse);
    expect(cadence.accept(1040000, 25), isTrue);
  });
}
