/// Phase-preserving sampling: a 30 fps camera can supply 25 fps, instead of
/// dropping to 15 fps by restarting a 40 ms timer after every accepted frame.
class CaptureCadence {
  int? _nextUs;
  bool accept(int captureUs, double fps) {
    final period = (1000000 / fps).round();
    final next = _nextUs;
    if (next != null && captureUs < next) return false;
    _nextUs = next == null || captureUs - next > period * 2
        ? captureUs + period
        : next + period;
    return true;
  }

  void reset() => _nextUs = null;
}
