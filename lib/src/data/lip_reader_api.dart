import 'package:dio/dio.dart';

import '../models/transcription_result.dart';
import '../models/reading_method.dart';
import '../models/transcript_rewrite.dart';
import 'settings_controller.dart';

class LipReaderApi {
  LipReaderApi(SettingsController settings, {Dio? dio})
    : this._(() => settings.apiUrl, dio);

  LipReaderApi.atAddress(String address, {Dio? dio})
    : this._(() => address, dio);

  LipReaderApi._(this._address, Dio? dio)
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: const Duration(seconds: 5),
              // A CPU-only server can need several minutes for a long clip,
              // especially while loading the model for the first request.
              sendTimeout: const Duration(minutes: 5),
              receiveTimeout: const Duration(minutes: 20),
            ),
          );

  final String Function() _address;
  String get apiUrl => _address();
  final Dio _dio;

  Future<Map<String, bool>> rewriteMethods() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$apiUrl/v1/rewrite-methods',
      options: Options(receiveTimeout: const Duration(seconds: 5)),
    );
    final methods = response.data?['methods'] as List? ?? const [];
    return {
      for (final method in methods)
        if (method is Map)
          method['id'].toString(): method['configured'] == true,
    };
  }

  Future<TranscriptRewrite> rewrite(String text, ReadingMethod method) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$apiUrl/v1/rewrites',
      data: {'text': text, 'method': method.id},
      options: Options(
        receiveTimeout: const Duration(seconds: 30),
        sendTimeout: const Duration(seconds: 5),
      ),
    );
    final value = TranscriptRewrite.fromJson(response.data ?? const {});
    if (value.method != method.id ||
        !{'completed', 'unchanged', 'unavailable'}.contains(value.status)) {
      throw const FormatException('Phản hồi AI không hợp lệ.');
    }
    return value;
  }

  Future<Map<String, dynamic>> health() async {
    if (apiUrl.isEmpty) {
      throw const FormatException('Nhập IP hiển thị trên VietLip Server.');
    }
    final response = await _dio.get<Map<String, dynamic>>(
      '$apiUrl/healthz',
      options: Options(
        receiveTimeout: const Duration(seconds: 5),
        sendTimeout: const Duration(seconds: 5),
      ),
    );
    return response.data ?? const {};
  }

  Future<TranscriptionResult> transcribe({
    required String videoPath,
    void Function(double progress)? onProgress,
    void Function(String status)? onStatus,
  }) async {
    Future<FormData> makeForm() async => FormData.fromMap({
      'video': await MultipartFile.fromFile(
        videoPath,
        filename: 'lip-reading.mp4',
      ),
      'input_kind': 'raw_face',
      'mode': 'visual_only',
    });

    try {
      onStatus?.call('Đang tải video lên máy chủ…');
      final accepted = await _dio.post<Map<String, dynamic>>(
        '$apiUrl/v1/jobs',
        data: await makeForm(),
        onSendProgress: (sent, total) {
          if (total > 0) onProgress?.call(sent / total);
        },
      );
      final jobId = accepted.data?['job_id']?.toString();
      if (jobId == null || jobId.isEmpty) {
        throw const FormatException('Máy chủ không trả mã lượt xử lý.');
      }
      final deadline = DateTime.now().add(const Duration(minutes: 20));
      while (DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(milliseconds: 800));
        final response = await _dio.get<Map<String, dynamic>>(
          '$apiUrl/v1/jobs/$jobId',
        );
        final payload = response.data ?? const <String, dynamic>{};
        final status = payload['status']?.toString() ?? '';
        if (status == 'queued') {
          final position = payload['queue_position'];
          onStatus?.call(
            position == null
                ? 'Đang chờ đến lượt xử lý…'
                : 'Đang chờ đến lượt xử lý · vị trí $position',
          );
          continue;
        }
        if (status == 'processing') {
          onStatus?.call('Máy chủ đang đọc chuyển động môi…');
          continue;
        }
        if (status == 'completed') {
          final result = payload['result'];
          if (result is! Map) {
            throw const FormatException('Kết quả xử lý không hợp lệ.');
          }
          onStatus?.call('Đã hoàn tất nhận dạng');
          return TranscriptionResult.fromJson(
            Map<String, dynamic>.from(result),
          );
        }
        if (status == 'failed') {
          final error = payload['error'];
          final message = error is Map ? error['message']?.toString() : null;
          throw FormatException(
            message ?? 'Máy chủ không thể hoàn tất lượt xử lý.',
          );
        }
        if (status == 'cancelled') {
          throw const FormatException('Lượt xử lý đã được hủy.');
        }
      }
      throw const FormatException(
        'Lượt xử lý vượt quá thời gian chờ. Hãy thử video ngắn hơn.',
      );
    } on DioException catch (error) {
      // Backward compatibility for an older companion server.
      if (error.response?.statusCode != 404) rethrow;
      onStatus?.call('Máy chủ đang đọc chuyển động môi…');
      final response = await _dio.post<Map<String, dynamic>>(
        '$apiUrl/v1/transcriptions',
        data: await makeForm(),
        onSendProgress: (sent, total) {
          if (total > 0) onProgress?.call(sent / total);
        },
      );
      return TranscriptionResult.fromJson(response.data ?? const {});
    }
  }

  static String readableError(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] != null) {
        final detail = data['detail'];
        if (detail is Map && detail['message'] != null) {
          return detail['message'].toString();
        }
        return detail.toString();
      }
      if (error.type == DioExceptionType.connectionError ||
          error.type == DioExceptionType.connectionTimeout) {
        return 'Kiểm tra IP, mở VietLip Server và kết nối hai thiết bị cùng Wi-Fi, rồi thử lại.';
      }
      if (error.type == DioExceptionType.sendTimeout) {
        return 'Tải video lên quá lâu. Hãy kiểm tra mạng và thử lại.';
      }
      if (error.type == DioExceptionType.receiveTimeout) {
        return 'Máy chủ xử lý quá lâu. Video chưa chắc đã lỗi; hãy thử đoạn ngắn hơn.';
      }
      if (error.type == DioExceptionType.badResponse) {
        return 'Máy chủ trả về lỗi ${error.response?.statusCode ?? 'không xác định'}.';
      }
    }
    if (error is FormatException) return error.message;
    return 'Chưa hoàn tất được thao tác. Hãy thử lại hoặc kiểm tra kết nối máy chủ.';
  }
}
