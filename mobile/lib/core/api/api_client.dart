import 'dart:async';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../storage/token_store.dart';
import 'api_exception.dart';

/// Thin wrapper over Dio that knows how to talk to the Django backend.
///
/// Responsibilities:
///  * attach the bearer token to every authenticated request;
///  * on a 401, refresh the access token **once** and replay the request;
///  * collapse concurrent refreshes into a single call, so ten parallel
///    requests failing at once produce one refresh, not ten;
///  * translate Dio errors into [ApiException].
class ApiClient {
  ApiClient({required TokenStore tokenStore, Dio? dio})
      : _tokenStore = tokenStore,
        _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = AppConfig.apiRoot
      ..connectTimeout = const Duration(seconds: 15)
      ..receiveTimeout = const Duration(seconds: 30)
      ..sendTimeout = const Duration(seconds: 60)
      ..headers['Accept'] = 'application/json'
      // Repeated query parameters must be `?status=a&status=b`, which is what
      // DRF's `request.query_params.getlist()` reads. Dio's default would
      // encode them as `status[]=a`, which the backend silently ignores —
      // producing unfiltered results rather than an error.
      ..listFormat = ListFormat.multi
      // DRF returns 4xx bodies we want to parse ourselves rather than have
      // Dio throw before we can read the field errors.
      ..validateStatus = (status) => status != null && status < 400;

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: _onRequest,
        onError: _onError,
      ),
    );
  }

  final Dio _dio;
  final TokenStore _tokenStore;

  /// Called when the refresh token itself is rejected — the user must sign in
  /// again. Wired up by the auth controller.
  FutureOr<void> Function()? onSessionExpired;

  /// In-flight refresh, shared by every request that 401s at the same time.
  Future<bool>? _refreshInFlight;

  Dio get raw => _dio;

  // ── Interceptors ──────────────────────────────────────────────────────────

  void _onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final skipAuth = options.extra['skipAuth'] == true;
    final token = _tokenStore.accessToken;
    if (!skipAuth && token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  Future<void> _onError(DioException error, ErrorInterceptorHandler handler) async {
    final response = error.response;
    final options = error.requestOptions;

    final shouldRefresh = response?.statusCode == 401 &&
        options.extra['skipAuth'] != true &&
        options.extra['isRetry'] != true;

    if (!shouldRefresh) {
      handler.next(error);
      return;
    }

    final refreshed = await _refreshAccessToken();
    if (!refreshed) {
      await onSessionExpired?.call();
      handler.next(error);
      return;
    }

    try {
      options.extra['isRetry'] = true;
      final token = _tokenStore.accessToken;
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      final retried = await _dio.fetch(options);
      handler.resolve(retried);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  /// Exchanges the stored refresh token for a new access token.
  /// Returns false when there is no refresh token or the server rejects it.
  Future<bool> _refreshAccessToken() {
    return _refreshInFlight ??= _performRefresh().whenComplete(() {
      _refreshInFlight = null;
    });
  }

  Future<bool> _performRefresh() async {
    final refresh = await _tokenStore.readRefreshToken();
    if (refresh == null || refresh.isEmpty) return false;

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh': refresh},
        options: Options(extra: {'skipAuth': true, 'isRetry': true}),
      );
      final access = response.data?['access'] as String?;
      if (access == null || access.isEmpty) return false;

      // SimpleJWT rotates the refresh token when ROTATE_REFRESH_TOKENS is on,
      // so persist a new one if the server sent it back.
      await _tokenStore.save(
        access: access,
        refresh: response.data?['refresh'] as String?,
      );
      return true;
    } on DioException {
      await _tokenStore.clear();
      return false;
    }
  }

  // ── Verbs ─────────────────────────────────────────────────────────────────

  Future<T> get<T>(
    String path, {
    Map<String, dynamic>? query,
    bool skipAuth = false,
  }) {
    return _send<T>(() => _dio.get<T>(
          path,
          queryParameters: query,
          options: Options(extra: {'skipAuth': skipAuth}),
        ));
  }

  Future<T> post<T>(
    String path, {
    Object? body,
    Map<String, dynamic>? query,
    bool skipAuth = false,
  }) {
    return _send<T>(() => _dio.post<T>(
          path,
          data: body,
          queryParameters: query,
          options: Options(extra: {'skipAuth': skipAuth}),
        ));
  }

  Future<T> patch<T>(String path, {Object? body}) {
    return _send<T>(() => _dio.patch<T>(path, data: body));
  }

  Future<T> delete<T>(String path, {Object? body}) {
    return _send<T>(() => _dio.delete<T>(path, data: body));
  }

  /// Multipart upload, used for incident evidence.
  Future<T> upload<T>(
    String path, {
    required FormData form,
    void Function(int sent, int total)? onProgress,
  }) {
    return _send<T>(() => _dio.post<T>(
          path,
          data: form,
          onSendProgress: onProgress,
          options: Options(contentType: 'multipart/form-data'),
        ));
  }

  Future<T> _send<T>(Future<Response<T>> Function() request) async {
    try {
      final response = await request();
      return response.data as T;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }
}
