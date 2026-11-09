package vn.lipread.lip_reader

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private val encoder = Executors.newSingleThreadExecutor()
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger,"vn.lipread/frame_encoder")
            .setMethodCallHandler { call, result ->
                if (call.method != "encode") { result.notImplemented(); return@setMethodCallHandler }
                val args = call.arguments as? Map<*, *>
                if (args == null) { result.error("invalid_frame","Missing camera frame",null); return@setMethodCallHandler }
                encoder.execute {
                    try {
                        val jpeg = FrameEncoder.encode(args)
                        runOnUiThread { result.success(jpeg) }
                    } catch (error: Exception) {
                        runOnUiThread { result.error("encode_failed",error.message,null) }
                    }
                }
            }
    }
    override fun onDestroy() {
        encoder.shutdown()
        super.onDestroy()
    }
}
