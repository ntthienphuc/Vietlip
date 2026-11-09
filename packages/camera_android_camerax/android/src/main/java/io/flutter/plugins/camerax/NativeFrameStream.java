package io.flutter.plugins.camerax;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.YuvImage;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import androidx.camera.core.ImageProxy;
import io.flutter.plugin.common.BinaryMessenger;
import io.flutter.plugin.common.EventChannel;
import io.flutter.plugin.common.MethodChannel;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Opt-in JPEG path: one native worker, at most two Dart events, no plane RPCs. */
final class NativeFrameStream implements EventChannel.StreamHandler {
  private final Handler main = new Handler(Looper.getMainLooper());
  private final ExecutorService worker = Executors.newSingleThreadExecutor();
  private final EventChannel events;
  private final MethodChannel control;
  private EventChannel.EventSink sink;
  private String sessionToken = "";
  private boolean busy;
  private long generation, serial, firstTimestamp, nextTimestamp;
  private final HashSet<Long> pending = new HashSet<>();
  private long intervalNs = 40_000_000;
  private long received, emitted, encodeNs;

  NativeFrameStream(BinaryMessenger messenger) {
    events = new EventChannel(messenger, "vn.lipread/native_frames");
    events.setStreamHandler(this);
    control = new MethodChannel(messenger, "vn.lipread/native_frames/control");
    control.setMethodCallHandler((call, result) -> {
      if (call.method.equals("ack")) {
        Number id = call.argument("id");
        if (id != null) pending.remove(id.longValue());
        result.success(null);
      } else result.notImplemented();
    });
  }

  @Override public void onListen(Object arguments, EventChannel.EventSink eventSink) {
    generation++;
    sink = eventSink;
    busy = false;
    pending.clear();
    firstTimestamp = nextTimestamp = 0;
    received = emitted = encodeNs = 0;
    if (arguments instanceof Map) {
      Object token = ((Map<?, ?>) arguments).get("sessionToken");
      sessionToken = token instanceof String ? (String) token : "";
      Object fps = ((Map<?, ?>) arguments).get("fps");
      if (fps instanceof Number) intervalNs = (long)(1e9 / Math.max(1, Math.min(30, ((Number)fps).doubleValue())));
    }
  }

  @Override public void onCancel(Object arguments) {
    generation++;
    sink = null;
    busy = false;
    pending.clear();
    Log.i("LipNativeFrames", "received=" + received + " emitted=" + emitted
        + " encode_ms=" + (emitted == 0 ? 0 : encodeNs / 1e6 / emitted));
  }

  // CameraX dispatches this analyzer on main. Encoding never runs on that thread.
  boolean offer(ImageProxy image) {
    if (sink == null) return false;
    received++;
    long timestamp = image.getImageInfo().getTimestamp();
    if (firstTimestamp == 0) firstTimestamp = timestamp;
    if (busy || pending.size() >= 2 || timestamp < nextTimestamp) {
      image.close();
      return true;
    }
    if (nextTimestamp == 0 || timestamp - nextTimestamp > intervalNs * 2) nextTimestamp = timestamp;
    nextTimestamp += intervalNs;
    busy = true;
    long epoch = generation;
    String token = sessionToken;
    long id = ++serial;
    pending.add(id);
    double capturedMs = (timestamp - firstTimestamp) / 1e6;
    worker.execute(() -> {
      long tick = System.nanoTime();
      try {
        int width = image.getWidth(), height = image.getHeight();
        if (id == 1) Log.i("LipNativeFrames", "source=" + width + "x" + height);
        byte[] nv21 = pack(image);
        byte[] jpeg;
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
          if (!new YuvImage(nv21, ImageFormat.NV21, width, height, null)
              .compressToJpeg(new Rect(0, 0, width, height), 80, output)) {
            throw new IllegalStateException("JPEG compression failed");
          }
          jpeg = output.toByteArray();
        }
        long elapsed = System.nanoTime() - tick;
        Map<String, Object> frame = new HashMap<>();
        frame.put("id", id);
        frame.put("sessionToken", token);
        frame.put("jpeg", jpeg);
        frame.put("capturedAtMs", capturedMs);
        frame.put("encodeMicros", elapsed / 1000);
        frame.put("rotationDegrees", image.getImageInfo().getRotationDegrees());
        main.post(() -> {
          if (generation == epoch && sink != null) {
            busy = false;
            emitted++;
            encodeNs += elapsed;
            sink.success(frame);
          }
        });
      } catch (Exception error) {
        main.post(() -> {
          if (generation == epoch) {
            busy = false;
            pending.remove(id);
            if (sink != null) sink.error("frame_encoding", error.getMessage(), null);
          }
        });
      } finally { image.close(); }
    });
    return true;
  }

  /** Handles padded rows and independent/overlapping chroma planes. */
  private static byte[] pack(ImageProxy image) {
    int width = image.getWidth(), height = image.getHeight();
    if ((width & 1) != 0 || (height & 1) != 0) throw new IllegalArgumentException("Odd YUV size");
    ImageProxy.PlaneProxy[] planes = image.getPlanes();
    if (planes.length < 3) throw new IllegalArgumentException("Expected YUV planes");
    byte[] packed = new byte[width * height * 3 / 2];
    for (int p = 0; p < 3; p++) {
      ByteBuffer source = planes[p].getBuffer().duplicate();
      int base = source.position(), rowStride = planes[p].getRowStride(), pixelStride = planes[p].getPixelStride();
      int rows = p == 0 ? height : height / 2, columns = p == 0 ? width : width / 2;
      byte[] row = new byte[rowStride];
      for (int y = 0; y < rows; y++) {
        if (p == 0 && pixelStride == 1) {
          source.position(base + y * rowStride);
          source.get(packed, y * width, width);
        } else {
          int offset = base + y * rowStride;
          source.position(offset);
          int count = Math.min(rowStride, source.limit() - offset);
          if (count < (columns - 1) * pixelStride + 1) throw new IllegalArgumentException("Short YUV plane");
          source.get(row, 0, count);
          for (int x = 0; x < columns; x++) {
            int dest = p == 0 ? y * width + x : width * height + y * width + x * 2 + (p == 1 ? 1 : 0);
            packed[dest] = row[x * pixelStride];
          }
        }
      }
    }
    return packed;
  }

  void dispose() {
    onCancel(null);
    events.setStreamHandler(null);
    control.setMethodCallHandler(null);
    worker.shutdown(); // Allow an owned ImageProxy to close in finally.
  }
}
