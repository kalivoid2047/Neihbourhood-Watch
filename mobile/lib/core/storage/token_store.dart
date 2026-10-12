import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists JWT credentials.
///
/// The refresh token goes to the platform keystore (Android Keystore /
/// iOS Keychain). The access token is held in memory only — it is short-lived
/// and a fresh one is minted from the refresh token on launch.
class TokenStore {
  TokenStore({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              // Defaults are AES-GCM with RSA-OAEP key wrapping in the Android
              // Keystore, which is what we want; `first_unlock` on iOS lets the
              // background poller read the token without the device unlocked.
              aOptions: AndroidOptions(),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock,
              ),
            );

  static const _refreshKey = 'nhw.refresh_token';

  final FlutterSecureStorage _storage;

  String? _accessToken;

  String? get accessToken => _accessToken;

  bool get hasAccessToken => _accessToken != null && _accessToken!.isNotEmpty;

  Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  Future<bool> hasSession() async {
    final refresh = await readRefreshToken();
    return refresh != null && refresh.isNotEmpty;
  }

  Future<void> save({required String access, String? refresh}) async {
    _accessToken = access;
    if (refresh != null && refresh.isNotEmpty) {
      await _storage.write(key: _refreshKey, value: refresh);
    }
  }

  void setAccessToken(String access) => _accessToken = access;

  Future<void> clear() async {
    _accessToken = null;
    await _storage.delete(key: _refreshKey);
  }
}
