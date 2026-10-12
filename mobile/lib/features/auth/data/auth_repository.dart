import '../../../core/api/api_client.dart';
import '../../../core/storage/token_store.dart';
import 'user.dart';

/// Talks to `apps.accounts` — registration, login, OTP, profile, contacts.
class AuthRepository {
  AuthRepository({required ApiClient api, required TokenStore tokens})
      : _api = api,
        _tokens = tokens;

  final ApiClient _api;
  final TokenStore _tokens;

  /// POST /api/auth/login — returns `{user, tokens: {access, refresh}}`.
  Future<AppUser> login({required String email, required String password}) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/login',
      body: {'email': email, 'password': password},
      skipAuth: true,
    );

    await _storeTokens(data['tokens']);
    return AppUser.fromJson((data['user'] as Map).cast<String, dynamic>());
  }

  /// POST /api/auth/register. The backend then expects OTP verification
  /// before the account is fully usable.
  Future<Map<String, dynamic>> register({
    required String email,
    required String fullName,
    required String phoneNumber,
    required String nationalId,
    required String password,
    String? address,
    double? latitude,
    double? longitude,
  }) async {
    return _api.post<Map<String, dynamic>>(
      '/auth/register',
      body: {
        'email': email,
        'full_name': fullName,
        'phone_number': phoneNumber,
        'national_id': nationalId,
        'password': password,
        if (address != null && address.isNotEmpty) 'address': address,
        'latitude': ?latitude,
        'longitude': ?longitude,
      },
      skipAuth: true,
    );
  }

  /// POST /api/auth/request-otp — `purpose` is `registration` or `login`.
  Future<void> requestOtp({
    required String email,
    String purpose = 'registration',
  }) async {
    await _api.post<Map<String, dynamic>>(
      '/auth/request-otp',
      body: {'email': email, 'purpose': purpose},
      skipAuth: true,
    );
  }

  /// POST /api/auth/verify-otp. Some backend configurations return a token
  /// pair on success, so store it when present.
  Future<AppUser?> verifyOtp({
    required String email,
    required String code,
    String purpose = 'registration',
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/verify-otp',
      body: {'email': email, 'code': code, 'purpose': purpose},
      skipAuth: true,
    );

    if (data['tokens'] != null) {
      await _storeTokens(data['tokens']);
    }
    final user = data['user'];
    return user is Map ? AppUser.fromJson(user.cast<String, dynamic>()) : null;
  }

  Future<void> forgotPassword(String email) async {
    await _api.post<Map<String, dynamic>>(
      '/auth/forgot-password',
      body: {'email': email},
      skipAuth: true,
    );
  }

  Future<void> resetPassword({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    await _api.post<Map<String, dynamic>>(
      '/auth/reset-password',
      body: {'email': email, 'code': code, 'new_password': newPassword},
      skipAuth: true,
    );
  }

  /// Blacklists the refresh token server-side, then clears local credentials.
  /// Local clearing happens even if the network call fails — the user asked to
  /// be signed out, and a dead network must not keep them signed in.
  Future<void> logout() async {
    final refresh = await _tokens.readRefreshToken();
    try {
      if (refresh != null && refresh.isNotEmpty) {
        await _api.post<Map<String, dynamic>>(
          '/auth/logout',
          body: {'refresh': refresh},
        );
      }
    } catch (_) {
      // Ignore — clearing locally is what matters.
    } finally {
      await _tokens.clear();
    }
  }

  /// Mints a fresh access token from the stored refresh token. Used on launch
  /// to restore a session without a login screen flash.
  Future<bool> restoreSession() async {
    final refresh = await _tokens.readRefreshToken();
    if (refresh == null || refresh.isEmpty) return false;

    try {
      final data = await _api.post<Map<String, dynamic>>(
        '/auth/refresh',
        body: {'refresh': refresh},
        skipAuth: true,
      );
      final access = data['access'] as String?;
      if (access == null) return false;
      await _tokens.save(access: access, refresh: data['refresh'] as String?);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<AppUser> currentUser() async {
    final data = await _api.get<Map<String, dynamic>>('/users/me');
    return AppUser.fromJson(data);
  }

  Future<AppUser> updateProfile(Map<String, dynamic> changes) async {
    final data = await _api.patch<Map<String, dynamic>>('/users/me', body: changes);
    return AppUser.fromJson(data);
  }

  // ── Emergency contacts ────────────────────────────────────────────────────

  Future<List<EmergencyContact>> emergencyContacts() async {
    final data = await _api.get<dynamic>('/me/emergency-contacts');
    final items = data is Map ? data['results'] as List? ?? const [] : data as List;
    return items
        .whereType<Map>()
        .map((e) => EmergencyContact.fromJson(e.cast<String, dynamic>()))
        .toList();
  }

  Future<EmergencyContact> addEmergencyContact(EmergencyContact contact) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/me/emergency-contacts',
      body: contact.toJson(),
    );
    return EmergencyContact.fromJson(data);
  }

  Future<void> deleteEmergencyContact(String id) async {
    await _api.delete<dynamic>('/me/emergency-contacts/$id');
  }

  Future<void> _storeTokens(dynamic tokens) async {
    if (tokens is! Map) return;
    final access = tokens['access'] as String?;
    if (access == null) return;
    await _tokens.save(access: access, refresh: tokens['refresh'] as String?);
  }
}
