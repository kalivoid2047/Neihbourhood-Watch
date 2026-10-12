import 'package:dio/dio.dart';

/// A network or API failure translated into something the UI can show.
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.fieldErrors = const {}});

  final String message;
  final int? statusCode;

  /// Per-field validation messages, keyed by the serializer field name.
  /// DRF returns these as `{"email": ["This field is required."]}`.
  final Map<String, String> fieldErrors;

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isValidation => statusCode == 400;

  /// Whether the failure looks like "the phone is offline", which callers use
  /// to decide between showing an error and falling back to cached data.
  bool get isConnectivity => statusCode == null;

  String? errorFor(String field) => fieldErrors[field];

  /// Builds an [ApiException] from a Dio error, unpacking DRF's error shapes.
  factory ApiException.fromDio(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiException('The server took too long to respond.');
      case DioExceptionType.connectionError:
        return ApiException(
          'Cannot reach the server. Check your connection and try again.',
        );
      case DioExceptionType.cancel:
        return ApiException('Request cancelled.');
      default:
        break;
    }

    final response = error.response;
    final status = response?.statusCode;
    final data = response?.data;

    if (data is Map) {
      final fieldErrors = <String, String>{};
      String? detail;

      data.forEach((key, value) {
        final text = _flatten(value);
        if (text == null) return;
        if (key == 'detail' || key == 'non_field_errors') {
          detail ??= text;
        } else {
          fieldErrors[key.toString()] = text;
        }
      });

      final message = detail ??
          (fieldErrors.isNotEmpty
              ? fieldErrors.values.first
              : _defaultMessageFor(status));
      return ApiException(message, statusCode: status, fieldErrors: fieldErrors);
    }

    return ApiException(_defaultMessageFor(status), statusCode: status);
  }

  static String? _flatten(dynamic value) {
    if (value == null) return null;
    if (value is String) return value;
    if (value is List) {
      final parts = value.map(_flatten).whereType<String>();
      return parts.isEmpty ? null : parts.join(' ');
    }
    if (value is Map) {
      final parts = value.values.map(_flatten).whereType<String>();
      return parts.isEmpty ? null : parts.join(' ');
    }
    return value.toString();
  }

  static String _defaultMessageFor(int? status) {
    if (status == null) {
      return 'Could not reach the server. Please try again.';
    }
    return switch (status) {
      400 => 'Some of the details you entered are not valid.',
      401 => 'Your session has expired. Please sign in again.',
      403 => 'You do not have permission to do that.',
      404 => 'We could not find what you were looking for.',
      429 => 'Too many attempts. Please wait a moment and try again.',
      >= 500 => 'The server ran into a problem. Please try again shortly.',
      _ => 'Something went wrong. Please try again.',
    };
  }

  @override
  String toString() => 'ApiException($statusCode): $message';
}
