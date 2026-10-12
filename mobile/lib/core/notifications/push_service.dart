import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../../features/alarm/data/alarm_store.dart';
import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../config/app_config.dart';

/// An incident id pushed to the device, plus whatever the server told us about
/// it. The client always re-fetches the incident before alarming — a push
/// payload is a hint, not a source of truth, and acting on unverified payload
/// data would let anyone who obtained the FCM key raise a siren.
class PushAlarmHint {
  const PushAlarmHint({
    required this.kind,
    this.incidentId,
    this.sosAlertId,
    this.title,
    this.body,
  });

  final String kind;
  final String? incidentId;
  final String? sosAlertId;

  /// Present on `test` pushes from `manage.py check_push`.
  final String? title;
  final String? body;

  bool get isAlarm => kind == 'incident_alert' || kind == 'sos_alert';

  /// A delivery check sent during setup — never sounds an alarm.
  bool get isTest => kind == 'test';

  static PushAlarmHint? from(Map<String, dynamic> data) {
    final kind = data['kind'] as String?;
    if (kind == null) return null;
    return PushAlarmHint(
      kind: kind,
      incidentId: data['incident_id'] as String?,
      sosAlertId: data['sos_alert_id'] as String?,
      title: data['title'] as String?,
      body: data['body'] as String?,
    );
  }
}

/// Firebase Cloud Messaging integration.
///
/// This is the *fast* path for alarms; [AlarmEngine]'s polling is the path
/// that always works. Everything here degrades gracefully: if Firebase is not
/// configured, or Play Services is missing, or the user denies notification
/// permission, the app still alarms via polling.
class PushService {
  PushService({required ApiClient api}) : _api = api;

  final ApiClient _api;

  bool _available = false;
  String? _token;

  /// Whether push is actually working on this device.
  bool get isAvailable => _available;
  String? get token => _token;

  /// Called with each push that carries an alarm hint.
  void Function(PushAlarmHint hint)? onAlarmHint;

  /// Initialises Firebase and wires up the message handlers.
  ///
  /// Returns false when push is unavailable for any reason — the caller should
  /// carry on regardless rather than treating it as fatal.
  Future<bool> initialise() async {
    if (!AppConfig.pushEnabled) {
      debugPrint('PushService: disabled by build configuration');
      return false;
    }

    try {
      // Reads android/app/google-services.json and ios/Runner/
      // GoogleService-Info.plist. Throws if neither is present.
      await Firebase.initializeApp();
    } catch (error) {
      debugPrint(
        'PushService: Firebase not configured ($error). '
        'Alarms will run on polling only.',
      );
      return false;
    }

    try {
      final messaging = FirebaseMessaging.instance;

      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        // Only honoured if Apple has granted the Critical Alerts entitlement
        // for this bundle id; harmless otherwise.
        criticalAlert: true,
      );

      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        debugPrint('PushService: notification permission denied');
        return false;
      }

      // Show our own notification for foreground messages so the alarm rules
      // decide how loud it is, rather than the OS rendering it for us.
      await messaging.setForegroundNotificationPresentationOptions(
        alert: false,
        badge: true,
        sound: false,
      );

      FirebaseMessaging.onMessage.listen(_handleMessage);
      FirebaseMessaging.onMessageOpenedApp.listen(_handleMessage);
      FirebaseMessaging.onBackgroundMessage(firebaseBackgroundHandler);

      _token = await messaging.getToken();
      messaging.onTokenRefresh.listen((token) {
        _token = token;
        unawaited(registerToken(token));
      });

      _available = true;
      return true;
    } catch (error) {
      debugPrint('PushService: initialisation failed — $error');
      return false;
    }
  }

  void _handleMessage(RemoteMessage message) {
    final hint = PushAlarmHint.from(message.data);
    if (hint != null) onAlarmHint?.call(hint);
  }

  /// Registers the FCM token against the signed-in user so the backend can
  /// target this device. Requires `POST /api/me/device-tokens` on the server
  /// (see `docs/FIREBASE_SETUP.md`).
  Future<void> registerToken([String? explicitToken]) async {
    final token = explicitToken ?? _token;
    if (token == null || token.isEmpty) return;

    try {
      await _api.post<dynamic>(
        '/me/device-tokens',
        body: {
          'token': token,
          'platform': defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android',
        },
      );
    } on ApiException catch (error) {
      // A 404 here means the backend endpoint has not been deployed yet. That
      // is expected before the Phase 5 backend change lands, and push simply
      // stays inactive until it does.
      if (error.isNotFound) {
        debugPrint(
          'PushService: /me/device-tokens not available on this server yet',
        );
      } else {
        debugPrint('PushService: token registration failed — ${error.message}');
      }
    }
  }

  /// Unregisters on sign-out, so the next user of this handset does not get
  /// the previous user's alerts.
  Future<void> unregisterToken() async {
    final token = _token;
    if (token == null) return;
    try {
      await _api.delete<dynamic>('/me/device-tokens', body: {'token': token});
    } catch (error) {
      debugPrint('PushService: token removal failed — $error');
    }
  }
}

/// Handles pushes that arrive while the app is terminated or backgrounded.
///
/// Runs in its own isolate, so it can only touch things that rebuild
/// themselves from disk. It records the incident id for the alarm engine and
/// lets the next poll (or the app opening) do the rest — doing a full
/// authenticated fetch here would race the token refresh.
@pragma('vm:entry-point')
Future<void> firebaseBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
  } catch (_) {
    // Already initialised in this isolate.
  }

  final hint = PushAlarmHint.from(message.data);
  if (hint == null || !hint.isAlarm) return;

  final incidentId = hint.incidentId;
  if (incidentId == null) return;

  // Shared preferences is the only thing both isolates can see, so park the id
  // there. The next poll, or the app opening, turns it into a real alarm.
  try {
    final store = await AlarmStore.open();
    await store.setPendingAlarm(incidentId);
  } catch (error) {
    debugPrint('Background push: could not record pending alarm — $error');
  }
}
