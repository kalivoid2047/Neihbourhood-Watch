/// Build-time configuration.
///
/// Values come from `--dart-define` so the same source builds dev, staging and
/// production. Example:
///
/// ```
/// flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
/// ```
class AppConfig {
  const AppConfig._();

  /// Base URL of the Django backend, without a trailing slash.
  ///
  /// The default targets the Android emulator's host loopback (10.0.2.2), which
  /// is where `python manage.py runserver` listens during development. On a
  /// physical device, pass your machine's LAN address instead.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  /// Environment label shown in Settings and attached to crash reports.
  static const String environment = String.fromEnvironment(
    'ENVIRONMENT',
    defaultValue: 'dev',
  );

  /// Set to false to build without Firebase Cloud Messaging. The alarm still
  /// works through polling; only the sub-second push path is disabled.
  static const bool pushEnabled = bool.fromEnvironment(
    'PUSH_ENABLED',
    defaultValue: true,
  );

  static bool get isProduction => environment == 'prod';

  /// All API paths hang off `/api`.
  static String get apiRoot => '$apiBaseUrl/api';
}
