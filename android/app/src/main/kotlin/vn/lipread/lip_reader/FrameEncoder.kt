package vn.lipread.lip_reader

import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import java.io.ByteArrayOutputStream

/** Converts CameraX planes off the UI thread, respecting both plane strides. */
object FrameEncoder {
    fun encode(args: Map<*, *>): ByteArray {
        val width = (args["width"] as Number).toInt()
        val height = (args["height"] as Number).toInt()
        require(width in 2..4096 && height in 2..4096)
        require(width % 2 == 0 && height % 2 == 0)
        val planes = args["planes"] as List<*>
        val format = args["format"] as String
        return if (format == "jpeg") {
            (planes[0] as Map<*, *>)["bytes"] as ByteArray
        } else if (format == "nv21") {
            val bytes = (planes[0] as Map<*, *>)["bytes"] as ByteArray
            require(bytes.size >= width * height * 3 / 2)
            ByteArrayOutputStream().use { stream ->
                check(YuvImage(bytes, ImageFormat.NV21, width, height, null)
                    .compressToJpeg(Rect(0,0,width,height),80,stream))
                stream.toByteArray()
            }
        } else {
            require(format == "yuv420" && planes.size >= 3)
            val packed = ByteArray(width * height * 3 / 2)
            for (planeIndex in 0..2) {
                val plane = planes[planeIndex] as Map<*, *>
                val bytes = plane["bytes"] as ByteArray
                val row = (plane["rowStride"] as Number).toInt()
                val pixel = (plane["pixelStride"] as Number).toInt()
                val planeWidth = if (planeIndex == 0) width else width / 2
                val planeHeight = if (planeIndex == 0) height else height / 2
                require((planeHeight-1)*row+(planeWidth-1)*pixel < bytes.size)
                for (y in 0 until planeHeight) {
                    if (planeIndex == 0 && pixel == 1) {
                        bytes.copyInto(packed, y*width, y*row, y*row+width)
                        continue
                    }
                    for (x in 0 until planeWidth) {
                        val target = if (planeIndex == 0) y*width+x else
                            width*height+y*width+x*2+(if (planeIndex == 1) 1 else 0)
                        packed[target] = bytes[y*row+x*pixel]
                    }
                }
            }
            ByteArrayOutputStream().use { stream ->
                check(YuvImage(packed, ImageFormat.NV21, width, height, null)
                    .compressToJpeg(Rect(0,0,width,height),80,stream))
                stream.toByteArray()
            }
        }
    }
}
