package vn.lipread.lip_reader

import android.app.Activity
import android.content.Context
import android.content.Intent
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.util.concurrent.Executors

/** Export only an app-owned capture to a destination selected by the user. */
class RecordingExporter(private val activity: Activity) {
    private val writer = Executors.newSingleThreadExecutor()
    private var pendingResult: MethodChannel.Result? = null
    private var pendingFile: File? = null

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        if (call.method != "exportRecording") {
            result.notImplemented()
            return
        }
        if (pendingResult != null) {
            result.error("export_busy", "An export is already in progress", null)
            return
        }
        try {
            val path = call.argument<String>("path") ?: error("Missing recording path")
            val recording = File(path).canonicalFile
            val captures = File(activity.getDir("flutter", Context.MODE_PRIVATE), "captures").canonicalFile
            require(recording.parentFile == captures && recording.extension.lowercase() == "mp4") {
                "Only VietLip recordings can be exported"
            }
            require(recording.isFile && recording.length() > 0) { "Recording no longer exists" }
            pendingFile = recording
            pendingResult = result
            val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "video/mp4"
                putExtra(Intent.EXTRA_TITLE, "VietLip_${recording.name}")
            }
            activity.startActivityForResult(intent, REQUEST_CODE)
        } catch (error: Exception) {
            pendingFile = null
            pendingResult = null
            result.error("export_unavailable", error.message, null)
        }
    }

    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode != REQUEST_CODE) return false
        val result = pendingResult ?: return true
        val recording = pendingFile
        val destination = data?.data
        if (resultCode != Activity.RESULT_OK || destination == null || recording == null) {
            pendingResult = null
            pendingFile = null
            result.success(false)
            return true
        }
        writer.execute {
            try {
                activity.contentResolver.openOutputStream(destination, "wt").use { output ->
                    checkNotNull(output) { "Cannot open the selected destination" }
                    recording.inputStream().use { input -> input.copyTo(output) }
                }
                activity.runOnUiThread {
                    pendingResult = null
                    pendingFile = null
                    result.success(true)
                }
            } catch (error: Exception) {
                activity.runOnUiThread {
                    pendingResult = null
                    pendingFile = null
                    result.error("export_failed", error.message, null)
                }
            }
        }
        return true
    }

    fun close() {
        writer.shutdown()
    }

    companion object {
        private const val REQUEST_CODE = 22092
    }
}
