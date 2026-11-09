package io.flutter.plugins.camerax;

import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import androidx.camera.core.SurfaceRequest;
import io.flutter.plugin.common.BinaryMessenger;
import io.flutter.plugin.common.EventChannel;
import java.util.HashMap;
import java.util.Map;

/** Actual Preview surface geometry, including CameraX StreamSharing changes. */
final class PreviewGeometryStream implements EventChannel.StreamHandler {
  private final EventChannel channel;
  private final Handler main = new Handler(Looper.getMainLooper());
  private final Map<Long, Map<String, Object>> latest = new HashMap<>();
  private final Map<Long, Long> generations = new HashMap<>();
  private EventChannel.EventSink sink;

  PreviewGeometryStream(BinaryMessenger messenger) {
    channel = new EventChannel(messenger, "vn.lipread/preview_geometry");
    channel.setStreamHandler(this);
  }

  void observe(long id, SurfaceRequest request, boolean handlesCropAndRotation) {
    final long generation = generations.getOrDefault(id, 0L) + 1;
    generations.put(id, generation);
    request.setTransformationInfoListener(main::post, info -> {
      if (!Long.valueOf(generation).equals(generations.get(id))) return;
      Rect crop = info.getCropRect();
      Map<String, Object> event = new HashMap<>();
      event.put("textureId", id);
      event.put("width", request.getResolution().getWidth());
      event.put("height", request.getResolution().getHeight());
      event.put("left", crop.left);
      event.put("top", crop.top);
      event.put("right", crop.right);
      event.put("bottom", crop.bottom);
      event.put("rotationDegrees", info.getRotationDegrees());
      event.put("mirroring", info.isMirroring());
      event.put("hasCameraTransform", info.hasCameraTransform());
      event.put("handlesCropAndRotation", handlesCropAndRotation);
      latest.put(id, event);
      Log.i("LipPreviewGeometry", event.toString());
      if (sink != null) sink.success(event);
    });
  }

  void release(long id) {
    generations.remove(id);
    latest.remove(id);
  }

  @Override public void onListen(Object arguments, EventChannel.EventSink eventSink) {
    sink = eventSink;
    for (Map<String, Object> value : latest.values()) sink.success(value);
  }

  @Override public void onCancel(Object arguments) { sink = null; }

  void dispose() {
    sink = null;
    latest.clear();
    generations.clear();
    channel.setStreamHandler(null);
  }
}
